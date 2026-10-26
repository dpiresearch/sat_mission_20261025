#!/usr/bin/env bash
# Point a Cloudflare-hosted domain (apex + www) at the CloudFront distribution from deploy.sh.
# Idempotent: requests/reuses an ACM cert, writes DNS-only CNAMEs in Cloudflare, waits for
# issuance, then attaches the aliases + cert to the distribution.
#
# Credentials: AWS from $CRED_CSV (as in deploy.sh); Cloudflare API_TOKEN from $CF_FILE.
set -euo pipefail

DOMAIN="${DOMAIN:-joansat.org}"
CRED_CSV="${CRED_CSV:-$HOME/.ssh/rootkey_20260421.csv}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF_FILE="${CF_FILE:-$ROOT/cloudflare_token.txt}"
source "$ROOT/deploy/state.env"   # DIST_ID, DIST_DOMAIN

IFS=, read -r AK SK < <(sed -n 2p "$CRED_CSV" | tr -d '\r\357\273\277')
export AWS_ACCESS_KEY_ID="$AK" AWS_SECRET_ACCESS_KEY="$SK" AWS_DEFAULT_REGION="us-east-1"
unset AWS_PROFILE AWS_SESSION_TOKEN

CF_TOKEN=$(grep '^API_TOKEN' "$CF_FILE" | sed -E 's/^[A-Z_]+[[:space:]]*[=:][[:space:]]*//' | tr -d '\r\n "')
cf() {  # cf METHOD PATH [JSON]
  curl -sf -X "$1" -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4$2" ${3:+--data "$3"}
}
ZONE=$(cf GET "/zones?name=$DOMAIN" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"][0]["id"])')

# upsert a DNS-only CNAME, replacing any existing record of that name
cname() {
  local name="${1%.}" target="${2%.}" ids
  ids=$(cf GET "/zones/$ZONE/dns_records?name=$name" | python3 -c \
    'import json,sys;print(" ".join(r["id"] for r in json.load(sys.stdin)["result"] if r["type"] in ("CNAME","A","AAAA")))')
  for id in $ids; do cf DELETE "/zones/$ZONE/dns_records/$id" >/dev/null; done
  cf POST "/zones/$ZONE/dns_records" \
    "{\"type\":\"CNAME\",\"name\":\"$name\",\"content\":\"$target\",\"proxied\":false,\"ttl\":300}" >/dev/null
  echo "DNS  $name -> $target"
}

# 1. ACM certificate (us-east-1, required by CloudFront)
CERT=$(aws acm list-certificates --certificate-statuses PENDING_VALIDATION ISSUED \
  --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn | [0]" --output text)
if [ "$CERT" = "None" ] || [ -z "$CERT" ]; then
  CERT=$(aws acm request-certificate --domain-name "$DOMAIN" --subject-alternative-names "www.$DOMAIN" \
    --validation-method DNS --tags Key=project,Value=dpi-ltm-cubesat --query CertificateArn --output text)
  echo "requested cert $CERT"
fi

# 2. validation records (ACM fills these in a few seconds after the request)
for _ in $(seq 20); do
  RECS=$(aws acm describe-certificate --certificate-arn "$CERT" \
    --query 'Certificate.DomainValidationOptions[].ResourceRecord.[Name,Value]' --output text)
  [ -n "$RECS" ] && [ "$RECS" != "None" ] && break; sleep 3
done
echo "$RECS" | sort -u | while read -r n v; do cname "$n" "$v"; done
echo "waiting for certificate to be issued..."
aws acm wait certificate-validated --certificate-arn "$CERT"
echo "cert issued"

# 3. attach aliases + cert to the distribution
aws cloudfront get-distribution-config --id "$DIST_ID" > /tmp/dist_cfg.json
ETAG=$(python3 -c 'import json;print(json.load(open("/tmp/dist_cfg.json"))["ETag"])')
python3 - "$DOMAIN" "$CERT" <<'EOF'
import json, sys
domain, cert = sys.argv[1:]
cfg = json.load(open("/tmp/dist_cfg.json"))["DistributionConfig"]
cfg["Aliases"] = {"Quantity": 2, "Items": [domain, "www." + domain]}
cfg["ViewerCertificate"] = {"ACMCertificateArn": cert, "SSLSupportMethod": "sni-only",
                            "MinimumProtocolVersion": "TLSv1.2_2021", "CertificateSource": "acm"}
json.dump(cfg, open("/tmp/dist_new.json", "w"))
EOF
aws cloudfront update-distribution --id "$DIST_ID" --if-match "$ETAG" \
  --distribution-config file:///tmp/dist_new.json >/dev/null
echo "distribution $DIST_ID now serves $DOMAIN, www.$DOMAIN"

# 4. site records
cname "$DOMAIN" "$DIST_DOMAIN"
cname "www.$DOMAIN" "$DIST_DOMAIN"
echo "Site: https://$DOMAIN/"
