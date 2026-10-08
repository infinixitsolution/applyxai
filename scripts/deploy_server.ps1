# Push the current branch to GitHub, then update the EC2 checkout.
$ErrorActionPreference = "Stop"

$Key = Join-Path $env:USERPROFILE ".ssh\new-applyxai-key.pem"
$Target = "ubuntu@ec2-32-237-22-143.ap-southeast-2.compute.amazonaws.com"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $Key)) {
    throw "SSH key not found: $Key"
}

Set-Location $RepoRoot
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq "HEAD") {
    throw "Detached HEAD. Check out a branch before deploying."
}

$dirty = git status --porcelain --untracked-files=no
if ($dirty) {
    Write-Host "Tracked files are not committed, so they will not be deployed:"
    Write-Host $dirty
    throw "Commit those changes, then run this script again."
}

Write-Host "Pushing $branch to origin..."
git push origin $branch

Write-Host "Updating the server..."
$updateScript = Join-Path $PSScriptRoot "update_server.sh"
$lfCopy = Join-Path $env:TEMP "update_server.sh"
[IO.File]::WriteAllText($lfCopy, ([IO.File]::ReadAllText($updateScript) -replace "`r`n", "`n"))
scp -i $Key -o StrictHostKeyChecking=accept-new $lfCopy "${Target}:/tmp/update_server.sh"
ssh -i $Key -o StrictHostKeyChecking=accept-new $Target "mkdir -p /home/ubuntu/applyxai/scripts && install -m 755 /tmp/update_server.sh /home/ubuntu/applyxai/scripts/update_server.sh && bash /home/ubuntu/applyxai/scripts/update_server.sh $branch"
