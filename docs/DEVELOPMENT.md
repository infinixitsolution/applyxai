# ApplyXAI — Local development

The repository contains the classic app and the new SaaS, which run side by side during the migration:

| | Classic control panel | ApplyXAI SaaS backend | ApplyXAI web app |
|---|---|---|---|
| Code | `app.py`, `runAiBot.py`, `config/`, `modules/`, `templates/` | `backend/` | `frontend/` (React, Vite, Tailwind) |
| Start | `python app.py` | `uvicorn backend.app.main:app --reload` | `npm run dev` in `frontend/` |
| URL | http://127.0.0.1:5000 | http://127.0.0.1:8000/api/docs | http://localhost:5173 |
| Config | `user_config.json` | `.env` (see `.env.example`) | `frontend/.env.local` (optional) |
| Storage | CSV files in `all excels/` | SQLite `storage/applyxai.db` or PostgreSQL | none (talks to the API) |

The classic panel is unchanged and keeps working; nothing in `backend/` imports `runAiBot.py`.

## One-time setup (Windows, PowerShell)

```powershell
cd C:\xampp\htdocs\applyxainew
python -m venv venv                     # skip if venv\ already exists
venv\Scripts\python -m pip install -r requirements.txt -r backend/requirements.txt -r requirements-dev.txt
copy .env.example .env                  # optional for development; defaults work without it
venv\Scripts\alembic -c backend/alembic.ini upgrade head
```

The one-click `start.bat` / `run_tests.bat` launchers use a separate `.venv\` and only install the classic panel's dependencies. That's fine: the backend tests skip themselves when FastAPI isn't installed.

## Running

```powershell
# classic control panel (unchanged workflow)
venv\Scripts\python app.py

# SaaS API, run from the project root
venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8000
```

Then open http://127.0.0.1:8000/api/docs for the interactive API docs. `GET /api/health` should return `{"success": true, ...}`.

The backend package is always imported as `backend.app.*` from the project root, because the classic panel already owns the module name `app` (`app.py`).

To copy your existing engine history (the CSVs in `all excels/`) into an ApplyXAI account:

```powershell
venv\Scripts\python -m backend.app.cli import-history --email you@example.com
```

How the SaaS drives the engine (run config, events, pause/stop) is described in `docs/AUTOMATION.md`.

### Web app

Needs Node.js 20 or newer. With the API running on port 8000:

```powershell
cd frontend
npm install        # first time only
npm run dev        # http://localhost:5173
```

Vite proxies `/api` to the API, so the browser sees one origin and the auth cookies work without CORS. To point at another API, set `APPLYXAI_API_URL` (for example `$env:APPLYXAI_API_URL="http://127.0.0.1:8077"`) before `npm run dev`. `VITE_CONTACT_EMAIL` in `frontend/.env.local` sets the support address shown on public pages.

In development, verification and password-reset emails are printed to the API console instead of being sent; open the link from there. Links use `FRONTEND_URL`, which defaults to `http://localhost:5173`.

`npm run build` writes a static bundle to `frontend/dist/`. Serving it in production (Nginx in front of the API) is covered in Phase 11.

## Tests

```powershell
venv\Scripts\python -m pytest                     # everything: engine + backend
venv\Scripts\python -m pytest tests               # engine and classic panel only
venv\Scripts\python -m pytest backend/tests       # SaaS backend only
```

Web app (from `frontend/`):

```powershell
npm run typecheck
npm test           # Vitest + Testing Library, no browser or API needed
npm run build
```

No test needs a real browser, network access, or a running database server. Optional extras:

- `OPENAI_API_KEY` enables the live AI smoke test.
- `TEST_POSTGRES_URL` also runs the migration test against PostgreSQL (see `docs/DATABASE.md`).

## Rules while the migration is in progress

- Keep `python app.py` working after every change, and keep the full test suite green.
- Don't modify `runAiBot.py` or `modules/` outside the planned Phase 7 hooks (see `docs/SAAS_ROADMAP.md`).
- Don't revert `chromedriver.exe` in `modules/open_chrome.py`. It's required on Windows.
- Never commit `.env`, `user_config.json`, `storage/`, or anything containing credentials.
