# Start ApplyXAI FastAPI on port 8010 (8000 is often used by other local tools).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "venv not found. Create it and pip install -r requirements.txt first." -ForegroundColor Red
    exit 1
}
$Port = if ($env:APPLYXAI_API_PORT) { $env:APPLYXAI_API_PORT } else { "8010" }
Write-Host "Applying database migrations..." -ForegroundColor DarkGray
& $Python -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migration failed. Fix errors above before starting the API." -ForegroundColor Red
    exit 1
}
Write-Host "ApplyXAI API -> http://127.0.0.1:$Port/api/docs" -ForegroundColor Cyan
& $Python -m uvicorn backend.app.main:app --reload --port $Port
