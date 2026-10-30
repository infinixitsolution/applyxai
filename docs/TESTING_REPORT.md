# ApplyXAI — Testing Report

**Date:** 2026-10-17 (combined re-run); 2026-10-16 (historical detail below)  
**Environment:** Windows 10, Python 3.12.10, `C:\xampp\htdocs\applyxainew\venv`

## Test counts (collect-only)

| Tree | Count | Command |
|------|-------|---------|
| `backend/tests` | **433** | `pytest backend\tests --collect-only` (2026-10-17) |
| `tests/` (engine) | **360** | `pytest tests --collect-only` (2026-10-17) |
| Combined (approx.) | **804** | Both trees via `pytest.ini` `testpaths`, `-m "not live"` |

Largest engine files: `test_question_matching.py` (50), `test_updater.py` (29), `test_selectors_groundtruth.py` (24), `test_h1b_sponsorship.py` (22), `test_ai_connections.py` (21), `test_agent.py` (20).

## Commands used

```powershell
cd C:\xampp\htdocs\applyxainew

# Backend (full)
venv\Scripts\python.exe -m pytest backend\tests -m "not live" -q --tb=line

# Engine (representative)
venv\Scripts\python.exe -m pytest tests\test_runaibot_fixes.py tests\test_selectors_groundtruth.py tests\test_automation_runner.py -q --tb=line

# Collection count
venv\Scripts\python.exe -m pytest backend\tests --collect-only -q
```

## Results summary

| Scope | Collected | Passed | Failed | Skipped | Duration (approx.) |
|-------|-----------|--------|--------|---------|---------------------|
| `backend/tests` + `tests/` (combined, `-m "not live"`) **2026-10-17** | **804** | **803** | **0** | **1** | **~168 s** |
| `backend/tests` only | 400 | 397 | 2 | 1 | ~176 s |
| `tests/` only (engine) | 352 | 328 | 24 | 0 | ~28.5 min |
| `backend/tests` + `tests/` (combined) **2026-10-16** | 752 | 707 | 44 | 1 | ~31 min |
| Engine sample (3 files) | 51 | 50 | 1 | 0 | ~6 s |

Command for combined run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests tests -m "not live" -q --tb=no
```

## Failures (detail)

### Combined run — current failures (2026-10-17)

None. Full combined `-m "not live"` run: **803 passed**, **0 failed**, **1 skipped** (PostgreSQL migration parity).

### `tests/` only — 24 failures (2026-10-16)

Same clusters as below except **no** `test_logging.py` or `test_driver_arch.py` failures in this isolated run (those appeared in the combined suite — possible import/order interaction).

### Combined run — failure clusters (42 engine + 2 backend)

| Area | Count | Typical cause |
|------|-------|----------------|
| `tests/test_agent.py` | 10 | `AttributeError` — agent/supervisor API drift vs tests |
| `tests/test_logging.py` | 16 | `print_lg` / handler behavior vs expectations |
| `tests/test_question_matching.py` | 11 | Text questions not filled / classification path |
| `tests/test_packaging.py` | 2 | Missing `_get_python_exe` export on `automation.runner` |
| `tests/test_driver_arch.py` | 2 | Codesign logging expectations |
| `tests/test_launch_and_humanize.py` | 1 | `try_xp` error reporting |
| `tests/test_runaibot_fixes.py` | 1 | First-name `human_type` path |
| `backend/tests/test_tailored_resume_limits.py` | 2 | Missing `pytest-asyncio` |

### 1. `test_tailored_resume_limits.py` (×2)

```
Failed: async def functions are not natively supported.
```

- **Cause:** Tests use `@pytest.mark.asyncio` but `pytest-asyncio` is not installed/configured.
- **Remediation:** Add `pytest-asyncio` to `requirements-dev.txt` and configure `asyncio_mode` in `pytest.ini`.

### 2. `test_runaibot_fixes.py::test_text_question_is_typed_through_human_type`

```
AssertionError: assert [] == [(text_input, bot.first_name)]
```

- **Cause:** `answer_questions` no longer routes first-name text through `human_type` as the test expects (behavior or test drift).
- **Remediation:** Align implementation with intended typing helper or update test to match current label-matching path.

## Skipped

| Test | Reason |
|------|--------|
| `test_migrations.py` (PostgreSQL variant) | `TEST_POSTGRES_URL` not set |

## Warnings observed

- Unknown `pytest.mark.asyncio` (same root cause as AUD-001).
- SQLAlchemy `compare_metadata` cycle warning between `applications` and `resumes`.

## Not run (this pass)

- Live OpenAI / provider tests (`@pytest.mark.live`).
- Full `tests/` directory in one invocation (risk of long runtime; prefer per-file).
- Playwright smokes (`npm run test:e2e` in `frontend/`; needs `E2E_EMAIL` / `E2E_PASSWORD`).
- Real LinkedIn automation (forbidden for audit safety).

## Frontend tests

- Vitest exists for some pages (e.g. `Applications.test.tsx`); not executed in this baseline pass.
- Run: `cd frontend && npm test` (see `frontend/package.json`).

## Regression policy

After each fix for AUD-001/AUD-002, re-run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests -m "not live"
venv\Scripts\python.exe -m pytest tests\test_runaibot_fixes.py tests\test_question_matching.py
```

See also [AUDIT.md](./AUDIT.md) §9.
