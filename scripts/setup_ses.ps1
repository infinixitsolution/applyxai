# Create Amazon SES for applyxai.com and print SMTP settings for no-reply@applyxai.com
# Prerequisites: AWS CLI, credentials with ses + iam permissions (admin or PowerUser+SES).
$ErrorActionPreference = "Stop"

$Region = "ap-southeast-2"
$Domain = "applyxai.com"
$From = "no-reply@applyxai.com"
$StackName = "applyxai-ses"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $RepoRoot "infra\ses-applyxai.yaml"

function Ensure-AwsCli {
    $aws = Get-Command aws -ErrorAction SilentlyContinue
    if ($aws) { return $aws.Source }
    $paths = @(
        "${env:ProgramFiles}\Amazon\AWSCLIV2\aws.exe",
        "${env:ProgramFiles(x86)}\Amazon\AWSCLIV2\aws.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    throw "AWS CLI not found. Install: winget install Amazon.AWSCLI"
}

$Aws = Ensure-AwsCli
Write-Host "Using AWS CLI: $Aws"
& $Aws sts get-caller-identity --region $Region | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "AWS credentials not configured. Run: aws configure (Access key, Secret, region $Region)"
}

Write-Host "Deploying CloudFormation stack $StackName in $Region ..."
$exists = & $Aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Aws cloudformation create-stack `
        --stack-name $StackName `
        --template-body "file:///$($Template -replace '\\','/')" `
        --parameters "ParameterKey=DomainName,ParameterValue=$Domain" "ParameterKey=MailFromAddress,ParameterValue=$From" `
        --capabilities CAPABILITY_NAMED_IAM `
        --region $Region
    Write-Host "Waiting for stack CREATE_COMPLETE (DNS records appear in outputs when ready)..."
    & $Aws cloudformation wait stack-create-complete --stack-name $StackName --region $Region
} else {
    Write-Host "Stack exists; updating template if changed..."
    & $Aws cloudformation update-stack `
        --stack-name $StackName `
        --template-body "file:///$($Template -replace '\\','/')" `
        --parameters "ParameterKey=DomainName,ParameterValue=$Domain" "ParameterKey=MailFromAddress,ParameterValue=$From" `
        --capabilities CAPABILITY_NAMED_IAM `
        --region $Region 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $Aws cloudformation wait stack-update-complete --stack-name $StackName --region $Region
    }
}

Write-Host "`n=== SES identity DNS (add at your DNS provider) ==="
& $Aws sesv2 get-email-identity --email-identity $Domain --region $Region --output json | Out-Host

Write-Host "`n=== Stack outputs (SMTP — store SecretAccessKey securely) ==="
& $Aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs" --output table

$secret = & $Aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='SmtpSecretAccessKey'].OutputValue" --output text
$user = & $Aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='SmtpUsername'].OutputValue" --output text
$hostName = "email-smtp.$Region.amazonaws.com"

if ($secret -and $user) {
    $smtpPass = & python (Join-Path $RepoRoot "scripts\ses_smtp_password.py") $secret $Region
    Write-Host "`n=== ApplyXAI .env (after domain shows Verified in SES) ==="
    Write-Host "SMTP_HOST=$hostName"
    Write-Host "SMTP_PORT=587"
    Write-Host "SMTP_USERNAME=$user"
    Write-Host "SMTP_PASSWORD=<derived below>"
    Write-Host "SMTP_FROM=ApplyXAI <$From>"
    Write-Host "SMTP_PASSWORD (derived): $smtpPass"
}

Write-Host "`nNext: add DKIM/verification DNS records, wait for Verified, request production access in SES if still in sandbox, restart applyxai-backend."
