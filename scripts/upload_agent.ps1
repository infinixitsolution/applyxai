# Copy built desktop agent binaries to EC2 (not in git — run after build_agent.ps1).
$ErrorActionPreference = "Stop"

$Key = Join-Path $env:USERPROFILE ".ssh\new-applyxai-key.pem"
$Target = "ubuntu@ec2-32-237-22-143.ap-southeast-2.compute.amazonaws.com"
$RemoteDir = "/home/ubuntu/applyxai/dist"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $Key)) {
    throw "SSH key not found: $Key"
}

$files = @()
foreach ($name in @("ApplyXAI-Agent-GUI.exe", "ApplyXAI-Agent.exe", "ApplyXAI-Agent-Setup.exe")) {
    $p = Join-Path (Join-Path $RepoRoot "dist") $name
    if (Test-Path -LiteralPath $p) { $files += Get-Item -LiteralPath $p }
}

if (-not $files.Count) {
    throw "No agent exes under $RepoRoot\dist. Run scripts\build_agent.ps1 first."
}

Write-Host "Uploading $($files.Count) file(s) to $RemoteDir ..."
ssh -i $Key -o StrictHostKeyChecking=accept-new $Target "mkdir -p $RemoteDir"
foreach ($f in $files) {
    Write-Host "  $($f.Name) ($([math]::Round($f.Length / 1MB, 1)) MB)"
    scp -i $Key -o StrictHostKeyChecking=accept-new $f.FullName "${Target}:${RemoteDir}/"
}
Write-Host "Done. Candidates can download via /api/automation/desktop-agent/download"
