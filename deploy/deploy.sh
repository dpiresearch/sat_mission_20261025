#!/usr/bin/env bash
# Deploy public/ to a private S3 bucket fronted by CloudFront (HTTPS, OAC).
# Idempotent: re-running syncs files and invalidates the cache.
#
# Credentials: read at runtime from $CRED_CSV (AWS console "Access key ID,Secret access key"
# CSV). Nothing is written to disk. Prefer a scoped IAM user over a root key.
set -euo pipefail

CRED_CSV="${CRED_CSV:-$HOME/.ssh/rootkey_20260421.csv}"
REGION="us-east-1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/deploy/state.env"

IFS=, read -r AK SK < <(sed -n 2p "$CRED_CSV" | tr -d '\r\357\273\277')
export AWS_ACCESS_KEY_ID="$AK" AWS_SECRET_ACCESS_KEY="$SK" AWS_DEFAULT_REGION="$REGION"
unset AWS_PROFILE AWS_SESSION_TOKEN

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="${BUCKET:-dpi-ltm-cubesat-mission-$ACCOUNT}"
[ -f "$STATE" ] && source "$STATE"

python3 "$ROOT/build.py"

# 1. private bucket
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" >/dev/null
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging 'TagSet=[{Key=project,Value=dpi-ltm-cubesat}]'
  echo "created bucket $BUCKET"
fi

# 2. upload
aws s3 sync "$ROOT/public/" "s3://$BUCKET/" --delete --exclude ".DS_Store" \
  --cache-control "public, max-age=300" >/dev/null
for f in $(cd "$ROOT/public" && find das_project -type f); do   # DAS files as downloadable text
  aws s3 cp "$ROOT/public/$f" "s3://$BUCKET/$f" --content-type "text/plain; charset=utf-8" \
    --cache-control "public, max-age=300" >/dev/null
done
echo "uploaded to s3://$BUCKET"

# 3. CloudFront origin access control + distribution
if [ -z "${DIST_ID:-}" ]; then
  OAC_ID=$(aws cloudfront create-origin-access-control --origin-access-control-config \
    "Name=$BUCKET-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query OriginAccessControl.Id --output text)
  cat > /tmp/dist.json <<EOF
{
  "CallerReference": "$BUCKET-$(date +%s)",
  "Comment": "DPI LTM CubeSat mission site",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "HttpVersion": "http2and3",
  "PriceClass": "PriceClass_100",
  "Origins": {"Quantity": 1, "Items": [{
    "Id": "s3-$BUCKET",
    "DomainName": "$BUCKET.s3.$REGION.amazonaws.com",
    "OriginAccessControlId": "$OAC_ID",
    "S3OriginConfig": {"OriginAccessIdentity": ""}
  }]},
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-$BUCKET",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true,
    "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}
  },
  "CustomErrorResponses": {"Quantity": 1, "Items": [
    {"ErrorCode": 403, "ResponsePagePath": "/error.html", "ResponseCode": "404", "ErrorCachingMinTTL": 60}
  ]}
}
EOF
  read -r DIST_ID DIST_DOMAIN < <(aws cloudfront create-distribution --distribution-config file:///tmp/dist.json \
    --query 'Distribution.[Id,DomainName]' --output text)
  printf 'BUCKET=%s\nDIST_ID=%s\nDIST_DOMAIN=%s\nOAC_ID=%s\n' "$BUCKET" "$DIST_ID" "$DIST_DOMAIN" "$OAC_ID" > "$STATE"
  echo "created distribution $DIST_ID ($DIST_DOMAIN)"

  # bucket policy: only this distribution may read
  cat > /tmp/policy.json <<EOF
{"Version": "2012-10-17", "Statement": [{
  "Sid": "AllowCloudFrontOAC", "Effect": "Allow",
  "Principal": {"Service": "cloudfront.amazonaws.com"},
  "Action": "s3:GetObject", "Resource": "arn:aws:s3:::$BUCKET/*",
  "Condition": {"StringEquals": {"AWS:SourceArn": "arn:aws:cloudfront::$ACCOUNT:distribution/$DIST_ID"}}
}]}
EOF
  aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/policy.json
else
  aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null
  echo "invalidated $DIST_ID"
fi

echo "Site: https://$DIST_DOMAIN/"
