# One-shot SES setup for ApplyXAI — run in Windows PowerShell (not inside Cursor only).
# Double-click or:  cd c:\xampp\htdocs\applyxainew  ;  .\scripts\complete_ses.ps1
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$Aws = "${env:ProgramFiles}\Amazon\AWSCLIV2\aws.exe"
if (-not (Test-Path $Aws)) { throw "Install AWS CLI first: winget install Amazon.AWSCLI" }

Write-Host "`n=== ApplyXAI Amazon SES setup ===" -ForegroundColor Cyan
Write-Host "Region: $Region  |  From: no-reply@applyxai.com  |  Domain: applyxai.com`n"

& $Aws configure set region $Region | Out-Null

$id = & $Aws sts get-caller-identity 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "You are not signed in to AWS yet." -ForegroundColor Yellow
    Write-Host "A browser window will open — sign in with the AWS account that owns EC2 (ap-southeast-2).`n"
    & $Aws login
    if ($LASTEXITCODE -ne 0) { throw "AWS login failed. Try: aws configure  (Access Key + Secret from IAM user)" }
}

& $Aws sts get-caller-identity | Out-Host

& (Join-Path $PSScriptRoot "setup_ses.ps1")

$OutFile = Join-Path $RepoRoot "ses-smtp.env"
$stack = "applyxai-ses"
$user = & $Aws cloudformation describe-stacks --stack-name $stack --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='SmtpUsername'].OutputValue" --output text 2>$null
$secret = & $Aws cloudformation describe-stacks --stack-name $stack --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='SmtpSecretAccessKey'].OutputValue" --output text 2>$null

if ($user -and $secret -and $secret -ne "None") {
    $pass = & python (Join-Path $RepoRoot "scripts\ses_smtp_password.py") $secret $Region
    @(
        "SMTP_HOST=email-smtp.$Region.amazonaws.com"
        "SMTP_PORT=587"
        "SMTP_USERNAME=$user"
        "SMTP_PASSWORD=$pass"
        "SMTP_FROM=ApplyXAI <no-reply@applyxai.com>"
    ) | Set-Content -Path $OutFile -Encoding UTF8
    Write-Host "`nWrote $OutFile (DO NOT commit to git)." -ForegroundColor Green

    $Key = Join-Path $env:USERPROFILE ".ssh\new-applyxai-key.pem"
    $Target = "ubuntu@ec2-32-237-22-143.ap-southeast-2.compute.amazonaws.com"
    if (Test-Path $Key) {
        $apply = Read-Host "Apply SMTP settings to production EC2 now? (y/N)"
        if ($apply -eq "y" -or $apply -eq "Y") {
            scp -i $Key $OutFile "${Target}:/tmp/ses-smtp.env"
            ssh -i $Key $Target @'
set -a; source /tmp/ses-smtp.env; set +a
ENV=/home/ubuntu/applyxai/.env
for k in SMTP_HOST SMTP_PORT SMTP_USERNAME SMTP_PASSWORD SMTP_FROM; do
  v="${!k}"
  if grep -q "^${k}=" "$ENV"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$ENV"
  else
    echo "${k}=${v}" >> "$ENV"
  fi
done
rm -f /tmp/ses-smtp.env
sudo systemctl restart applyxai-backend
sudo systemctl is-active applyxai-backend
'@
            Write-Host "Production .env updated and backend restarted." -ForegroundColor Green
        }
    }
}

Write-Host @"

IMPORTANT — DNS (one time):
  1. Open AWS Console → SES → Verified identities → applyxai.com
  2. Copy the DKIM CNAME records into your domain DNS (where you bought applyxai.com)
  3. Add SPF TXT: v=spf1 include:amazonses.com ~all
  4. Wait until SES shows Verified (often 15–60 minutes)
  5. If account is in Sandbox, request Production access in SES

Until DNS is verified, emails will not deliver even with SMTP set.

"@ -ForegroundColor Yellow
