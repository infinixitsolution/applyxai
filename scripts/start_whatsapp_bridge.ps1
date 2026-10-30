# Restart ApplyXAI WhatsApp bridge (port 39219) with current server.js (includes GET /chats).
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BridgeDir = Join-Path $RepoRoot "whatsapp-bridge"

$killed = @{}
foreach ($c in @(Get-NetTCPConnection -LocalPort 39219 -State Listen -ErrorAction SilentlyContinue)) {
    $procId = $c.OwningProcess
    if ($procId -and -not $killed[$procId]) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        $killed[$procId] = $true
    }
}

# Puppeteer can leave Chrome running after the bridge exits — blocks the next QR session.
foreach ($p in Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue) {
    if ($p.CommandLine -match "ApplyXAI[\\/]whatsapp-session") {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 2

$env:APPLYXAI_API_URL = if ($env:APPLYXAI_API_URL) { $env:APPLYXAI_API_URL } else { "http://127.0.0.1:8010" }
$envFile = Join-Path $RepoRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*WHATSAPP_BRIDGE_SECRET=(.+)$') {
            $env:WHATSAPP_BRIDGE_SECRET = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}
if (-not $env:WHATSAPP_BRIDGE_SECRET) {
    $env:WHATSAPP_BRIDGE_SECRET = "dev-whatsapp-bridge-local"
    Write-Host "WHATSAPP_BRIDGE_SECRET not in .env - using local dev default for inbound chat." -ForegroundColor Yellow
    Write-Host "Add WHATSAPP_BRIDGE_SECRET=dev-whatsapp-bridge-local to .env (must match the API)." -ForegroundColor DarkGray
}

Push-Location $BridgeDir
if (-not (Test-Path "node_modules")) {
    npm install
}
Write-Host "Starting WhatsApp bridge on http://127.0.0.1:39219 (Ctrl+C to stop)..." -ForegroundColor Cyan
Write-Host 'If chats fail with detached Frame, try: $env:WHATSAPP_HEADLESS="0"; node server.js' -ForegroundColor DarkGray
node server.js
