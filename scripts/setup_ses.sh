#!/usr/bin/env bash
# Same as setup_ses.ps1 for Linux/macOS. Requires aws CLI and configured credentials.
set -euo pipefail

REGION="${AWS_REGION:-ap-southeast-2}"
DOMAIN="${SES_DOMAIN:-applyxai.com}"
FROM="${SES_FROM:-no-reply@applyxai.com}"
STACK="${SES_STACK_NAME:-applyxai-ses}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$ROOT/infra/ses-applyxai.yaml"

command -v aws >/dev/null || { echo "Install AWS CLI: https://aws.amazon.com/cli/" >&2; exit 1; }
aws sts get-caller-identity --region "$REGION"

if ! aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" >/dev/null 2>&1; then
  aws cloudformation create-stack \
    --stack-name "$STACK" \
    --template-body "file://$TEMPLATE" \
    --parameters "ParameterKey=DomainName,ParameterValue=$DOMAIN" "ParameterKey=MailFromAddress,ParameterValue=$FROM" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"
  aws cloudformation wait stack-create-complete --stack-name "$STACK" --region "$REGION"
else
  aws cloudformation update-stack \
    --stack-name "$STACK" \
    --template-body "file://$TEMPLATE" \
    --parameters "ParameterKey=DomainName,ParameterValue=$DOMAIN" "ParameterKey=MailFromAddress,ParameterValue=$FROM" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" 2>/dev/null || true
fi

echo "=== DNS records for $DOMAIN ==="
aws sesv2 get-email-identity --email-identity "$DOMAIN" --region "$REGION"

aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --query "Stacks[0].Outputs" --output table

SECRET="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='SmtpSecretAccessKey'].OutputValue" --output text)"
USER="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='SmtpUsername'].OutputValue" --output text)"
if [[ -n "$SECRET" && "$SECRET" != "None" ]]; then
  PASS="$("$ROOT/venv/bin/python" "$ROOT/scripts/ses_smtp_password.py" "$SECRET" "$REGION" 2>/dev/null || python3 "$ROOT/scripts/ses_smtp_password.py" "$SECRET" "$REGION")"
  echo ""
  echo "SMTP_HOST=email-smtp.${REGION}.amazonaws.com"
  echo "SMTP_PORT=587"
  echo "SMTP_USERNAME=$USER"
  echo "SMTP_PASSWORD=$PASS"
  echo "SMTP_FROM=ApplyXAI <$FROM>"
fi
