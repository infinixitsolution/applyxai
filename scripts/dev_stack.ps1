# Open two terminals: FastAPI (8010) + Vite (5173).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Api = Join-Path $Root "scripts\dev_api.ps1"
$Fe = Join-Path $Root "scripts\dev_frontend.ps1"
Write-Host "Starting ApplyXAI dev stack..." -ForegroundColor Cyan
Write-Host "  API:       http://127.0.0.1:8010/api/docs"
Write-Host "  Frontend:  http://127.0.0.1:5173"
Write-Host ""
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $Api
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $Fe
