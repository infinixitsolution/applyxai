# Run production ops verify on EC2 via SSH (read-only checks).
$ErrorActionPreference = "Stop"
$Key = Join-Path $env:USERPROFILE ".ssh\new-applyxai-key.pem"
$Target = "ubuntu@ec2-32-237-22-143.ap-southeast-2.compute.amazonaws.com"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $Key)) {
    throw "SSH key not found: $Key"
}

$localScript = Join-Path $PSScriptRoot "verify_production_ops.sh"
$remote = Join-Path $env:TEMP "verify_production_ops.sh"
[IO.File]::WriteAllText($remote, ([IO.File]::ReadAllText($localScript) -replace "`r`n", "`n"))

scp -i $Key -o StrictHostKeyChecking=accept-new $remote "${Target}:/tmp/verify_production_ops.sh"
ssh -i $Key -o StrictHostKeyChecking=accept-new $Target "chmod +x /tmp/verify_production_ops.sh && APP_DIR=/home/ubuntu/applyxai bash /tmp/verify_production_ops.sh"
