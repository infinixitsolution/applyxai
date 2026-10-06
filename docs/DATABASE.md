# ApplyXAI — Database

SQLAlchemy 2.0 models in `backend/app/models/`, migrations in `backend/alembic/versions/`.
Production uses PostgreSQL; local development and tests default to SQLite (`storage/applyxai.db`).

## Conventions

- Primary keys are UUIDs (`id`). Every table has `created_at` / `updated_at` (UTC, timezone-aware).
- Every user-owned table has a non-null, indexed `user_id` with `ON DELETE CASCADE`. Deleting a user removes all of their data except the shared `jobs` catalogue.
- Status columns are stored as lowercase strings with a CHECK constraint (not native Postgres enums), so adding a status is a normal migration.
- Lists and free-form settings are `JSON` (`JSONB` on PostgreSQL).
- Constraint and index names follow a fixed naming convention (`backend/app/models/base.py`) so Alembic can alter them later.

## Tables

| Table | Purpose | Notable constraints |
|---|---|---|
| `users` | Accounts | unique `email` (stored lower-cased) |
| `user_profiles` | Phone, headline, summary, skills, preferred roles/locations, experience | one per user |
| `search_configs` | Job-search preferences fed to the engine | one per user; enumerated fields hold the engine's exact strings |
| `resumes` | Uploaded resume metadata (files live under `STORAGE_DIR`) | unique `storage_path`; partial unique index: one `is_default` per user |
| `jobs` | Shared catalogue of postings | unique `(platform, external_id)`; indexes on `external_id`, `platform`, `company`, `title`, `discovered_at` |
| `applications` | A user's outcome for a job | unique `(user_id, job_id)`; status ∈ discovered, queued, running, applied, failed, skipped, external, cancelled |
| `automation_jobs` | One automation run | status ∈ queued, running, paused, completed, failed, cancelled; partial unique index: one queued/running/paused run per user |
| `plans` | Plan catalogue (limits + price) | unique `code` |
| `subscriptions` | A user's plan subscription | unique `provider_subscription_id`; status ∈ pending, trialing, active, past_due, cancelled, expired |
| `usage_counters` | Monthly usage per user | unique `(user_id, period)`, period = `YYYY-MM` |

`jobs` has no `user_id` on purpose. User-facing queries must always reach jobs **through the user's own `applications`**, never by listing `jobs` directly.

### Search configuration values

`search_configs.experience_level`, `job_type`, and `on_site` store the exact strings the engine clicks on LinkedIn, as listed in `modules/validator.py`:

- Experience level: `Internship`, `Entry level`, `Associate`, `Mid-Senior level`, `Director`, `Executive`
- Job type: `Full-time`, `Part-time`, `Contract`, `Temporary`, `Volunteer`, `Internship`, `Other`
- Work setting: `On-site`, `Remote`, `Hybrid`

Never numeric IDs (`"1"`) or synonyms (`"permanent"`). API validation against these lists arrives in Phase 4.

## Running migrations

All commands run from the project root with the virtual environment's Python.

```powershell
# apply all migrations (uses DATABASE_URL, or SQLite by default)
venv\Scripts\alembic -c backend/alembic.ini upgrade head

# current revision / history
venv\Scripts\alembic -c backend/alembic.ini current
venv\Scripts\alembic -c backend/alembic.ini history

# after changing a model: generate, then REVIEW the file before committing
venv\Scripts\alembic -c backend/alembic.ini revision --autogenerate -m "describe change"

# roll back one step
venv\Scripts\alembic -c backend/alembic.ini downgrade -1
```

`backend/tests/test_migrations.py` fails if the migrations and the models ever disagree, and checks that a full downgrade removes everything.

## Using PostgreSQL locally

PostgreSQL 18 is installed on the Windows development machine. Create a database and user once (in `psql` as `postgres`):

```sql
CREATE USER applyxai WITH PASSWORD 'choose-a-password';
CREATE DATABASE applyxai OWNER applyxai;
CREATE DATABASE applyxai_test OWNER applyxai;
```

Then in `.env`:

```
DATABASE_URL=postgresql+psycopg://applyxai:choose-a-password@127.0.0.1:5432/applyxai
```

To also run the migration test against PostgreSQL:

```powershell
$env:TEST_POSTGRES_URL = "postgresql+psycopg://applyxai:choose-a-password@127.0.0.1:5432/applyxai_test"
venv\Scripts\python -m pytest backend/tests/test_migrations.py
```
