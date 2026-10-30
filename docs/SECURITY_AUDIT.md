# ApplyXAI — Security Audit Supplement

**Date:** 2026-10-16  
**Canonical implementation doc:** [SECURITY.md](./SECURITY.md)  
**Master audit:** [AUDIT.md](./AUDIT.md)

## Scope

Risk-based review of the **SaaS backend**, **agent API**, **classic panel**, and **desktop worker** configuration. No destructive penetration testing; no production traffic.

## Controls verified (design + tests)

| Area | Implementation | Test / evidence |
|------|----------------|-----------------|
| Password hashing | Argon2id | `test_auth_api.py`, SECURITY.md |
| Session tokens | JWT access + opaque refresh, rotation | `test_auth_api.py`, `test_two_factor_api.py` |
| CSRF | Double-submit cookie + header | API middleware, client sends `X-CSRF-Token` |
| CORS | Allow-list | `settings.cors_origins` |
| IDOR / isolation | User-scoped queries | `test_isolation.py` |
| Admin routes | `require_admin` on router | `test_admin_api.py` |
| Payment webhooks | HMAC / signature helpers | `test_razorpay_util.py`, `test_billing_api.py` |
| Resume upload | Type/size limits, optional ClamAV | `test_resumes_api.py`, `test_resume_malware_scan.py` |
| Production guards | Refuse start without PG, SMTP, payment, Redis RL | `test_settings.py` |
| Classic panel | Localhost bind, Host/Origin checks | SECURITY.md § Classic |

## Findings

| ID | Sev | Topic | Notes |
|----|-----|-------|-------|
| SEC-001 | P1 | Production checklist incomplete | Razorpay live keys, Redis rate limit, sign-off — see BACKLOG |
| SEC-002 | P2 | CSP enforcement | **Done in repo** (`Content-Security-Policy` in nginx snippet); deploy on host (BACKLOG #37) |
| SEC-003 | P2 | Agent device tokens | Pairing codes expire; verify rotation policy in ops docs |
| SEC-004 | P3 | Classic `user_config.json` | Plaintext secrets on disk — expected for legacy local mode |
| SEC-005 | P2 | Dependency CVEs | Run `pip audit` / Dependabot in CI (not executed this pass) |

## Out of scope (explicit)

- CAPTCHA bypass or anti-bot evasion research.
- LinkedIn ToS compliance legal review.
- Third-party penetration test report.

## Residual risk statement

With **development defaults** (`PAYMENT_PROVIDER=null`, SQLite, in-memory rate limits), the stack is suitable for **local dev only**. Production deployment must satisfy startup guards and [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md).
