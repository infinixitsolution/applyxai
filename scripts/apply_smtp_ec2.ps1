# Apply Amazon SES SMTP to production EC2 from a local env file (never commit).
# 1. In AWS SES (ap-southeast-2) → SMTP settings → Create SMTP credentials
# 2. Derive password: python scripts/ses_smtp_password.py <IAM_SECRET> ap-southeast-2
# 3. Save as ses-smtp.env next to this script (see ses-smtp.env.example)
# 4. Run: .\scripts\apply_smtp_ec2.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepoRoot "ses-smtp.env"
$Example = Join-Path $RepoRoot "ses-smtp.env.example"
$Key = Join-Path $env:USERPROFILE ".ssh\new-applyxai-key.pem"
$Target = "ubuntu@ec2-32-237-22-143.ap-southeast-2.compute.amazonaws.com"

if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path $Example)) { throw "Missing $EnvFile — copy from ses-smtp.env.example and fill in SES SMTP credentials." }
    Copy-Item $Example $EnvFile
    Write-Host "Created $EnvFile — edit it with your SES SMTP username and password, then run this script again." -ForegroundColor Yellow
    exit 1
}

$lines = Get-Content $EnvFile | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' }
$required = @("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
$vars = @{}
foreach ($line in $lines) {
    $k, $v = $line -split '=', 2
    $vars[$k.Trim()] = $v.Trim()
}
foreach ($k in $required) {
    if (-not $vars[$k]) { throw "ses-smtp.env is missing $k" }
}
if ($vars["SMTP_PASSWORD"] -match '^(YOUR_|paste|example|<)') {
    throw "Replace placeholder SMTP_PASSWORD in ses-smtp.env with the derived SES SMTP password."
}

Write-Host "Uploading SMTP settings to EC2 (password not shown)..."
scp -i $Key $EnvFile "${Target}:/tmp/ses-smtp.env"
ssh -i $Key $Target @'
set -e
ENV=/home/ubuntu/applyxai/.env
set -a
source /tmp/ses-smtp.env
set +a
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
echo "SMTP applied. From: $(grep ^SMTP_FROM= $ENV)"
'@
Write-Host "Done. Test in Admin -> Settings -> Email & SMTP." -ForegroundColor Green
