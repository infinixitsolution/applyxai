# ApplyXAI — Database Audit

**Date:** 2026-10-16  
**ORM:** SQLAlchemy 2.x under `backend/app/models/`  
**Migrations:** Alembic — `backend/alembic/versions/` (33 files)

## Engines

| Environment | Connection | Notes |
|-------------|------------|-------|
| Development | SQLite `storage/applyxai.db` | Default when `DATABASE_URL` empty |
| Production | PostgreSQL (`postgresql+psycopg://…`) | **Required** when `APP_ENV=production` |
| Migration test | Optional PostgreSQL | Set `TEST_POSTGRES_URL` for parity run |

## Core entities (inventory)

| Model file | Primary entities |
|------------|------------------|
| `user.py` | Users, roles, onboarding, token_version |
| `auth_token.py` | Refresh / email / reset tokens (hashed) |
| `application.py` | Applications, status, job linkage |
| `job.py` | Shared job catalogue |
| `resume.py` | User resumes, templates |
| `preferences.py` | Search + application preference blobs |
| `automation.py` | Runs, devices, logs, sources |
| `agent.py`, `agent_connect.py` | Agent devices, pairing |
| `subscription.py`, `billing.py`, `usage.py` | Plans, payments, quotas |
| `notification.py` | In-app notifications |
| `platform_settings.py` | Tenant-wide settings |
| `admin.py` | Audit log |
| `mock_interview.py`, `live_interview.py` | Interview products |
| `institute.py`, `partner.py` | B2B portals |

## Integrity checks

| Check | Status |
|-------|--------|
| Alembic upgrade head on SQLite | Tested via `test_migrations.py` |
| Alembic on PostgreSQL | Skipped without `TEST_POSTGRES_URL` |
| FK cycle applications ↔ resumes | **Warning** in compare_metadata — review before new FKs |
| UTC timestamps | Convention in models/services — verify per-field in code review |
| User ownership on rows | Enforced in services; validated by `test_isolation.py` |

## Migration practice

```powershell
venv\Scripts\alembic -c backend/alembic.ini upgrade head
venv\Scripts\alembic -c backend/alembic.ini revision --autogenerate -m "description"
```

**Rule:** Never drop production databases to fix migration conflicts; use forward fixes and backups ([PRODUCTION_OPS.md](./PRODUCTION_OPS.md)).

See [DATABASE.md](./DATABASE.md) for operator documentation.
