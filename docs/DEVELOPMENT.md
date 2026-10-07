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

### Desktop agent and background tasks

To try a full run locally, start the API and the web app, sign in, open **Automation → Connect a computer**, and pair this machine with the code it shows:

```powershell
venv\Scripts\python -m agent pair --server http://localhost:5173 --code ABCD-2345
venv\Scripts\python -m agent run
```

This launches the real engine, which opens Chrome and applies on LinkedIn with your account. Tick **Practice run** to fill in forms without submitting them. Use `--home <folder>` (or `APPLYXAI_AGENT_HOME`) to keep a test agent separate from your normal one. The commands the Connect dialog shows use `VITE_AGENT_SERVER_URL`, or the page's own address if that isn't set.

The periodic tasks (failing runs whose computer went silent, deleting expired pairing codes) run in Celery and need Redis:

```powershell
venv\Scripts\celery -A backend.app.worker worker --beat --pool=solo --loglevel=info
```

Without the worker, the Automation page still cleans up the signed-in user's stale runs when it loads, so development works without Redis.

### Payments

With the default `PAYMENT_PROVIDER=null`, choosing a plan on the Billing page activates it at once without any payment (the page says it's in test mode). This is for development only; production refuses to start with it.

To try real Razorpay checkout in test mode:

1. In the Razorpay Dashboard (Test Mode), create API keys and a webhook pointing at `https://<public-url>/api/billing/webhook/razorpay` with the `subscription.*` events. Locally, expose port 8000 with a tunnel (for example ngrok) for the webhook; checkout itself works without it.
2. In `.env`: `PAYMENT_PROVIDER=razorpay`, `PAYMENT_KEY_ID=rzp_test_...`, `PAYMENT_SECRET=...`, `PAYMENT_WEBHOOK_SECRET=...`.
3. Create the plans at Razorpay (once; it stores their IDs in the `plans` table):

```powershell
venv\Scripts\python -m backend.app.cli sync-plans
```

Prices come from the `plans` table, seeded from `backend/app/core/plans.py` (`seed-plans` does only that). Change prices and limits on the admin Plans page: a new price creates a new Razorpay plan for new subscribers, and existing subscribers stay on the old one.

### Admin area

Give an account admin access (register and verify it first), then sign in and open http://localhost:5173/admin. Admins land there after signing in; the header links between the admin area and the regular app.

```powershell
venv\Scripts\python -m backend.app.cli make-admin --email you@example.com
venv\Scripts\python -m backend.app.cli make-admin --email you@example.com --revoke   # take it away
```

The System page shows how email is delivered and can send a test email; it reports the mail server's error if delivery fails. To send real email in development, set `SMTP_HOST`, `SMTP_PORT` (587 for STARTTLS, 465 for SSL), `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` in `.env` and restart the API (Gmail needs an App Password). From a user's page you can resend their verification email or mark the address verified.

The System page pings the Celery workers through Redis; without Redis it shows "Unreachable" after about two seconds, and everything else still works.

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
- Don't modify `runAiBot.py` or `modules/` outside the planned engine hooks (`modules/run_hooks.py`; see `docs/AUTOMATION.md`).
- Tests never launch the real engine; they use fakes or a stand-in script that emits the same events.
- Don't revert `chromedriver.exe` in `modules/open_chrome.py`. It's required on Windows.
- Never commit `.env`, `user_config.json`, `storage/`, or anything containing credentials.
