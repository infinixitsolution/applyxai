# Start Vite on http://127.0.0.1:5173 (proxies /api -> port 8010).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "frontend")
Write-Host "ApplyXAI frontend -> http://127.0.0.1:5173" -ForegroundColor Cyan
npm run dev
