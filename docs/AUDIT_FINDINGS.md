# ApplyXAI — Audit Findings Register

**Last updated:** 2026-10-24  
**Master report:** [AUDIT.md](./AUDIT.md)

Severity: **P0** critical · **P1** high · **P2** medium · **P3** low

| ID | Sev | Component | Finding | Evidence | Status |
|----|-----|-----------|---------|----------|--------|
| AUD-001 | P2 | `backend/tests/test_tailored_resume_limits.py` | Async tests fail: `async def functions are not natively supported` | Re-verified 2026-10-17: 4 passed with project pytest asyncio config | **Closed** 2026-10-17 |
| AUD-002 | P2 | `runAiBot.py` / `answer_questions` | `test_text_question_is_typed_through_human_type` fails (no typing recorded) | Re-run 2026-10-24 passed | **Closed** 2026-10-24 |
| AUD-003 | P2 | `tests/` + `backend/tests` | Combined suite (`-m "not live"`): **0 failures** / **804** tests (~168 s) | `venv\Scripts\python.exe -m pytest backend\tests tests -m "not live" -q` 2026-10-17 | **Closed** — 803 passed, 1 skipped (PG migration) |
| AUD-011 | P2 | `tests/test_agent.py` | 10 failures — AttributeError vs current supervisor/runner | Isolated re-run 2026-10-24 passed | **Closed** 2026-10-24 |
| AUD-012 | P2 | `tests/test_logging.py` | 16 failures — logging helper contract drift | Isolated re-run 2026-10-24 passed | **Closed** 2026-10-24 |
| AUD-013 | P2 | `tests/test_question_matching.py` | 11 failures — text field answers empty | Isolated re-run 2026-10-24 passed | **Closed** 2026-10-24 |
| AUD-014 | P3 | `tests/test_packaging.py` | Isolated import / temp-dir round trip | Fixed `from modules import open_chrome` + keyring-isolated save/load | **Closed** 2026-10-24 |
| AUD-015 | P2 | `backend/tests/test_mock_interviews_api.py` | `test_turn_idempotent_with_client_turn_id` — `TURN_CONFLICT` on replay | Link reply via `meta.client_turn_id` + timestamp fallbacks in `_turn_response_for_idempotency` | **Closed** 2026-10-17 |
| AUD-016 | P2 | `backend/tests/test_settings.py` | `test_valid_production_configuration` — missing `WHATSAPP_BRIDGE_SECRET` | Gate secret on `OUTREACH_AUTOMATION_ENABLED`; test fixture updated | **Closed** 2026-10-17 |
| AUD-004 | P1 | Production ops | Launch blockers tracked in BACKLOG: Razorpay prod, Redis rate limits, backups, security sign-off | [BACKLOG.md](./BACKLOG.md) Phase 1 | **Open** |
| AUD-005 | P3 | Documentation | External audit prompt cites port **8000**; repo standard is **8010** | `.env.example`, `dev_api.ps1`, `DEVELOPMENT.md` | **Open** (doc only) |
| AUD-006 | P3 | Dev env | Two venv conventions: `venv/` (SaaS) vs `.venv/` (`start.bat`) | ARCHITECTURE_AUDIT historical note | **Accepted** |
| AUD-007 | P2 | Easy Apply | Live LinkedIn UI drift causes "Problem in Easy Applying" | User reports; mitigations in `clickers_and_finders.py` | **Mitigated** — monitor |
| AUD-008 | P2 | PostgreSQL | Migration test against PG skipped unless `TEST_POSTGRES_URL` | `test_migrations.py` skip | **Open** for CI |
| AUD-009 | P3 | Schema | Alembic warns on FK cycle `applications` ↔ `resumes` | Migration test warning | **Open** — review constraints |
| AUD-010 | P1 | Payments | `PAYMENT_PROVIDER=null` in dev; production startup enforces real provider | `backend/app/core/config.py`, `.env.example` | **By design** |

## Template for new findings

```
### AUD-XXX — [Title]
- **Severity:** P?
- **Affected:** path / endpoint / route
- **Evidence:** test output, log, reproduction
- **Expected:** …
- **Actual:** …
- **Root cause:** …
- **Fix:** …
- **Regression test:** …
- **Verified:** date / command
```
