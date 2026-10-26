#!/usr/bin/env bash
# Deploy the mission chatbot: Lambda (Python 3.13) + function URL + DynamoDB rate-limit table.
# Idempotent: re-running rebuilds the package and updates code/config.
# Credentials are read at runtime from $CRED_CSV, as in deploy.sh.
set -euo pipefail

CRED_CSV="${CRED_CSV:-$HOME/.ssh/rootkey_20260421.csv}"
REGION="us-east-1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/deploy/chat_state.env"
FN="dpi-ltm-chat"
ROLE="dpi-ltm-chat-lambda"
TABLE="dpi-ltm-chat-ratelimit"
SITE_ORIGINS="${SITE_ORIGINS:-https://joansat.org,https://www.joansat.org,https://dudeb310vkbf8.cloudfront.net}"
RESERVED_CONCURRENCY="${RESERVED_CONCURRENCY:-5}"

IFS=, read -r AK SK < <(sed -n 2p "$CRED_CSV" | tr -d '\r\357\273\277')
export AWS_ACCESS_KEY_ID="$AK" AWS_SECRET_ACCESS_KEY="$SK" AWS_DEFAULT_REGION="$REGION"
unset AWS_PROFILE AWS_SESSION_TOKEN
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# 1. package: refresh the knowledge base, then vendor Linux wheels next to the handler
python3 "$ROOT/build.py" >/dev/null
PKG="$ROOT/build/chat_pkg"
rm -rf "$PKG" "$ROOT/build/chat.zip" && mkdir -p "$PKG"
python3 -m pip install -q --no-compile --target "$PKG" --platform manylinux2014_x86_64 \
  --implementation cp --python-version 3.13 --only-binary=:all: "anthropic[bedrock]" boto3
cp "$ROOT/chat/handler.py" "$ROOT/chat/knowledge.md" "$PKG/"
(cd "$PKG" && find . -name "__pycache__" -prune -exec rm -rf {} + && zip -qr9 "$ROOT/build/chat.zip" .)
echo "package: $(du -h "$ROOT/build/chat.zip" | cut -f1)"

# 2. rate-limit table (on-demand, TTL)
if ! aws dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  aws dynamodb create-table --table-name "$TABLE" --billing-mode PAY_PER_REQUEST \
    --attribute-definitions AttributeName=k,AttributeType=S --key-schema AttributeName=k,KeyType=HASH \
    --tags Key=project,Value=dpi-ltm-cubesat >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE"
  aws dynamodb update-time-to-live --table-name "$TABLE" \
    --time-to-live-specification Enabled=true,AttributeName=expires_at >/dev/null
  echo "created table $TABLE"
fi

# 3. execution role: logs, the rate table, and Claude via Bedrock (Mantle + runtime)
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --tags Key=project,Value=dpi-ltm-cubesat --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "created role $ROLE"; sleep 10
fi
cat > /tmp/chat_policy.json <<EOF
{"Version": "2012-10-17", "Statement": [
  {"Sid": "Claude", "Effect": "Allow",
   "Action": ["bedrock-mantle:*", "bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
   "Resource": "*"},
  {"Sid": "RateTable", "Effect": "Allow", "Action": ["dynamodb:UpdateItem"],
   "Resource": "arn:aws:dynamodb:$REGION:$ACCOUNT:table/$TABLE"}
]}
EOF
aws iam put-role-policy --role-name "$ROLE" --policy-name chat-access --policy-document file:///tmp/chat_policy.json
ROLE_ARN="arn:aws:iam::$ACCOUNT:role/$ROLE"

ENV="{\"Variables\":{\"RATE_TABLE\":\"$TABLE\",\"ALLOWED_ORIGINS\":\"$SITE_ORIGINS\",\"PER_IP_PER_HOUR\":\"20\",\"GLOBAL_PER_DAY\":\"400\",\"MODEL\":\"anthropic.claude-opus-5-5\",\"FALLBACK_MODEL\":\"anthropic.claude-opus-4-8\",\"BEDROCK_REGION\":\"$REGION\"}}"

# 4. function
if aws lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --zip-file "fileb://$ROOT/build/chat.zip" >/dev/null
  aws lambda wait function-updated --function-name "$FN"
  aws lambda update-function-configuration --function-name "$FN" --environment "$ENV" --timeout 120 --memory-size 1024 >/dev/null
  aws lambda wait function-updated --function-name "$FN"
  echo "updated function $FN"
else
  for i in 1 2 3 4 5; do   # a new role can take a few seconds to become assumable
    if aws lambda create-function --function-name "$FN" --runtime python3.13 --architectures x86_64 \
        --handler handler.lambda_handler --role "$ROLE_ARN" --zip-file "fileb://$ROOT/build/chat.zip" \
        --timeout 120 --memory-size 1024 --environment "$ENV" --tags project=dpi-ltm-cubesat >/dev/null 2>/tmp/cf.err; then
      break
    fi
    grep -q "cannot be assumed" /tmp/cf.err || { cat /tmp/cf.err; exit 1; }
    sleep 8
  done
  aws lambda wait function-active-v2 --function-name "$FN"
  echo "created function $FN"
fi
aws lambda put-function-concurrency --function-name "$FN" --reserved-concurrent-executions "$RESERVED_CONCURRENCY" >/dev/null

# 5. public function URL; CORS restricted to the site origins
CORS="{\"AllowOrigins\":[\"${SITE_ORIGINS//,/\",\"}\"],\"AllowMethods\":[\"POST\"],\"AllowHeaders\":[\"content-type\"],\"MaxAge\":3600}"
if aws lambda get-function-url-config --function-name "$FN" >/dev/null 2>&1; then
  aws lambda update-function-url-config --function-name "$FN" --auth-type NONE --cors "$CORS" >/dev/null
else
  aws lambda create-function-url-config --function-name "$FN" --auth-type NONE --cors "$CORS" >/dev/null
  aws lambda add-permission --function-name "$FN" --statement-id public-url \
    --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE >/dev/null
fi
# Public function URLs also need lambda:InvokeFunction scoped to URL invocations (AWS CLI 2.27 lacks the flag)
python3 - "$FN" <<'PY'
import sys, boto3
c = boto3.client("lambda")
try:
    c.add_permission(FunctionName=sys.argv[1], StatementId="public-url-invoke", Action="lambda:InvokeFunction",
                     Principal="*", InvokedViaFunctionUrl=True)
except c.exceptions.ResourceConflictException:
    pass
PY
URL=$(aws lambda get-function-url-config --function-name "$FN" --query FunctionUrl --output text)
printf 'CHAT_URL=%s\nFUNCTION=%s\nTABLE=%s\nROLE=%s\n' "$URL" "$FN" "$TABLE" "$ROLE" > "$STATE"
echo "Chat API: $URL"
