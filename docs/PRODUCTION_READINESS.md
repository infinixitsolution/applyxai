# ApplyXAI — Production Readiness

**Date:** 2026-10-17  
**Decision:** **Not ready for unrestricted public launch** without closing P0 items in [P0_LAUNCH_CHECKLIST.md](./P0_LAUNCH_CHECKLIST.md).  
**Master audit:** [AUDIT.md](./AUDIT.md) · **Feature backlog:** [BACKLOG.md](./BACKLOG.md) · **Open/partial inventory:** [PENDING_PARTIAL_WORK.md](./PENDING_PARTIAL_WORK.md)

## Status legend

| Label | Meaning |
|-------|---------|
| Implemented | Code exists in main branch |
| Tested locally | Verified in dev environment this audit |
| Deployed | Not verified in this pass |
| Blocked | Requires external config or sign-off |

## Checklist

| Item | Status | Notes |
|------|--------|-------|
| PostgreSQL + migrations | Implemented | PG parity test optional |
| Secret keys (`SECRET_KEY`, `JWT_SECRET`) | Implemented | Enforced in production |
| SMTP for auth emails | Implemented | Required in production |
| `PAYMENT_PROVIDER=razorpay` | Implemented | Live keys + webhook secret (BACKLOG #32) |
| Redis rate limiting | Implemented | Must not use `memory://` in prod |
| Redis + Celery workers | Implemented | See DEVELOPMENT.md |
| HTTPS reverse proxy | Ops | Nginx/Caddy — [PRODUCTION_OPS.md](./PRODUCTION_OPS.md) |
| CORS / FRONTEND_URL | Implemented | Env configuration |
| ClamAV resume scan | Partial | Optional `CLAMAV_*` |
| Backups | Partial | Scripts exist; enable on host |
| Security sign-off | Blocked | [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) |
| CI all tests green | Implemented | 803/804 pass combined `-m "not live"` (1 PG skip); AUD-001/015/016 closed 2026-10-17 |
| Desktop installer signed | Deferred | Code signing backlog |
| Monitoring / alerting | Partial | Health endpoint; expand per ops |
| Deploy smoke | Implemented | `smoke_production.sh` fails `update_server.sh` on check failure |

## Release blockers

See **[P0_LAUNCH_CHECKLIST.md](./P0_LAUNCH_CHECKLIST.md)** (BACKLOG #17, #32, #34, #36, #37, #40, #43). Do not mix with outreach or mock-interview feature items (BACKLOG Phase 2b / Phase 2).

## Safe beta criteria

Can proceed to **limited beta** when:

1. PostgreSQL + Redis + Razorpay **sandbox** configured on staging.
2. Isolation tests pass (`test_isolation.py`).
3. Agent + desktop installer tested on a clean Windows VM.
4. Known test failures (AUD-001, AUD-002) fixed or waived with documented risk.

## Post-launch monitoring

- `GET /api/health` — liveness + DB + version marker.
- Admin runs view — failed automation inspection.
- Worker heartbeat / device last-seen — stale run recovery.

See [BACKLOG.md](./BACKLOG.md) for ongoing workstreams.
