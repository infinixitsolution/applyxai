# ApplyXAI — P0 launch checklist

**Purpose:** Track **production launch blockers only** — separate from product feature backlog ([BACKLOG.md](./BACKLOG.md) Phases 2–4 and institute outreach Phase 2b).

**Last updated:** 2026-10-17

## How to use

- Check items off in your ops runbook or ticket system; this file stays the **canonical list of P0 IDs**.
- Feature work (mock interview POC, outreach chat sync, Stripe subscriptions, analytics) belongs in [BACKLOG.md](./BACKLOG.md), not here.
- Security and infra sign-off use [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) and [PRODUCTION_OPS.md](./PRODUCTION_OPS.md).

## P0 items (from BACKLOG Phase 1)

| ID | Item | Status | Owner / evidence |
|----|------|--------|------------------|
| 17 | Security checklist sign-off | Partial | Template filled + dated approval |
| 32 | Production Razorpay (live keys, webhooks) | Open | [DEVELOPMENT.md](./DEVELOPMENT.md), `PAYMENT_PROVIDER=razorpay` |
| 34 | PostgreSQL backups to S3 + tested restore | Partial | `backup_postgres.sh`, timer on host |
| 36 | ClamAV resume scanning enabled or waived | Partial | `CLAMAV_*` or sign-off waiver |
| 37 | CSP enforced (after Report-Only review) | **Done in repo** | Deploy `applyxai-security-headers.conf` on the host |
| 40 | Redis-backed rate limits in production | Open | `RATE_LIMIT_STORAGE_URL` ≠ `memory://` |
| 43 | Full security checklist completion | Open | Same as #17 |

**Deferred (not P0 for first launch):** #22 code signing — track under Phase 3 agent release.

## Pre-launch verification commands

```powershell
# Combined tests (803 passed, 0 failed, 1 skipped as of 2026-10-17 — see TESTING_REPORT.md)
venv\Scripts\python.exe -m pytest backend\tests tests -m "not live" -q --tb=line

# Production ops script (on server)
./scripts/verify_production_ops.sh
```

## Related audit

- Test snapshot: [TESTING_REPORT.md](./TESTING_REPORT.md), [AUDIT_FINDINGS.md](./AUDIT_FINDINGS.md) (AUD-003, AUD-004)
- Overall readiness: [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md)
