# ApplyXAI — Local development

The repository contains two applications that run side by side during the migration:

| | Classic control panel | ApplyXAI SaaS backend |
|---|---|---|
| Code | `app.py`, `runAiBot.py`, `config/`, `modules/`, `templates/` | `backend/` |
| Start | `python app.py` | `uvicorn backend.app.main:app --reload` |
| URL | http://127.0.0.1:5000 | http://127.0.0.1:8000/api/docs |
| Config | `user_config.json` | `.env` (see `.env.example`) |
| Storage | CSV files in `all excels/` | SQLite `storage/applyxai.db` or PostgreSQL |

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

## Tests

```powershell
venv\Scripts\python -m pytest                     # everything: engine + backend
venv\Scripts\python -m pytest tests               # engine and classic panel only
venv\Scripts\python -m pytest backend/tests       # SaaS backend only
```

No test needs a real browser, network access, or a running database server. Optional extras:

- `OPENAI_API_KEY` enables the live AI smoke test.
- `TEST_POSTGRES_URL` also runs the migration test against PostgreSQL (see `docs/DATABASE.md`).

## Rules while the migration is in progress

- Keep `python app.py` working after every change, and keep the full test suite green.
- Don't modify `runAiBot.py` or `modules/` outside the planned Phase 7 hooks (see `docs/SAAS_ROADMAP.md`).
- Don't revert `chromedriver.exe` in `modules/open_chrome.py`. It's required on Windows.
- Never commit `.env`, `user_config.json`, `storage/`, or anything containing credentials.
