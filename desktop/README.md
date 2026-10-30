# ApplyXAI Desktop

Electron shell for the full ApplyXAI web app with an embedded automation worker.

## Development (default until production deploy)

Desktop loads **`http://127.0.0.1:5173`** (local Vite). Start the stack first:

```powershell
# Terminal 1 — API
cd ..
venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8010

# Terminal 2 — frontend (proxies /api to 8010)
cd frontend
npm run dev

# Terminal 3 — desktop
cd desktop
npm run build
npm start
```

Optional: `python -m agent.desktop_worker` if not using the bundled worker.

Guest UI in the app is **login / register only** (no marketing landing). Use **Visit website** for the public site.

### Production-style desktop (bundled SPA + cloud API)

```powershell
$env:APPLYXAI_DESKTOP_LOCAL = "0"
$env:APPLYXAI_CLOUD_API = "https://applyxai.com"
npm start
```

## Release

From the repo root:

```powershell
# Dev desktop installer (default API http://127.0.0.1:8010 — run .\scripts\dev_api.ps1 first)
.\scripts\build_desktop.ps1

# Production installer (API https://applyxai.com)
$env:APPLYXAI_DESKTOP_RELEASE = "1"
.\scripts\build_desktop.ps1
# or: .\scripts\build_desktop.ps1 -Release
```
