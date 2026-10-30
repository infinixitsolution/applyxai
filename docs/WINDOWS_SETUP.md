# ApplyXAI — Windows Setup (Verified)

**Date:** 2026-10-16  
**Project root:** `C:\xampp\htdocs\applyxainew`

## Prerequisites

- Python 3.12+ (project uses 3.12.10)
- Node.js 18+ (frontend / desktop build)
- Git (optional)

## One-time setup

```powershell
cd C:\xampp\htdocs\applyxainew
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt -r backend\requirements.txt -r requirements-dev.txt
copy .env.example .env
venv\Scripts\alembic -c backend\alembic.ini upgrade head
cd frontend
npm ci
cd ..\desktop
npm ci
```

## Daily development

### Terminal 1 — API (port 8010)

```powershell
cd C:\xampp\htdocs\applyxainew
.\scripts\dev_api.ps1
```

Verify: `GET http://127.0.0.1:8010/api/health` → `"automation_poll":"resume-idle-v2"`.

Override port: `$env:APPLYXAI_API_PORT = "8010"`.

### Terminal 2 — Frontend

```powershell
cd C:\xampp\htdocs\applyxainew\frontend
npm run dev
```

Open: http://localhost:5173 — routes `/app/profile`, `/app/questions`, `/app/settings/automation`.

Ensure `frontend/.env.local` or Vite proxy targets **8010** if not using defaults in `vite.config`.

### Desktop app (optional)

```powershell
cd C:\xampp\htdocs\applyxainew
.\scripts\build_desktop.ps1
# Install dist\ApplyXAI-Desktop-Setup.exe
```

Dev launcher without reinstall: `dist\ApplyXAI-Launch.bat`.

## Classic panel (legacy)

```powershell
venv\Scripts\python app.py
```

→ http://127.0.0.1:5000 — does **not** use `.env` SaaS config.

## Automation troubleshooting

```powershell
.\scripts\kill_extra_workers.ps1   # agent-worker, chromedriver, extra Chrome
```

Only **one** ApplyXAI Desktop window; avoid parallel `python -m agent run`.

## Tests

```powershell
venv\Scripts\python -m pytest backend\tests -m "not live"
venv\Scripts\python -m pytest tests\test_selectors_groundtruth.py
```

## Clean shutdown

1. Stop uvicorn (Ctrl+C).
2. Stop Vite (Ctrl+C).
3. Close ApplyXAI Desktop.
4. Run `kill_extra_workers.ps1` if Chrome/agent linger.

See [DEVELOPMENT.md](./DEVELOPMENT.md) for Celery/Redis and agent pairing.
