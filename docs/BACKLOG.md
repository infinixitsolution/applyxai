# ApplyXAI — Product backlog

**Canonical tracker** for incomplete features, partial implementations, tests, and production readiness.  
**Last updated:** 2026-10-12 (ops runbook + CI + verify scripts).

Related docs: [MOCK_INTERVIEW_IMPLEMENTATION_PLAN.md](./MOCK_INTERVIEW_IMPLEMENTATION_PLAN.md) (mock interview WPs done), [SITE_AUDIT.md](./SITE_AUDIT.md) (deploy smoke), [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) (agent + sign-off), [SAAS_ROADMAP.md](./SAAS_ROADMAP.md) (historical architecture proposal).

## Architecture non-goals

- **Server-side Chrome / browser farms** (SaaS roadmap Option B): not planned. Job discovery and Easy Apply run on the **user’s desktop agent** ([AUTOMATION.md](./AUTOMATION.md)).
- **LinkedIn job discovery inside the SPA** (#2): same as above unless product explicitly changes execution model.

## Intentional — not defects

| Item | Location | Notes |
|------|----------|--------|
| `NullProvider` / `NOT_SUPPORTED` | `backend/app/services/payments/null.py` | Expected when payments disabled in dev |
| JSON parse `pass` in mock interview parsers | `mock_interview_service.py` | Fall-through to repair/retry |
| `except OSError: pass` on temp file delete | `resume_service.py` | Best-effort cleanup |
| Stripe checkout not wired | `stripe_provider.py` | Admin can select Stripe; returns `STRIPE_NOT_READY` until Checkout ships |

---

## Phase 1 — P0 launch blockers

| ID | Item | Status | Workstream | Notes |
|----|------|--------|------------|--------|
| 15 | Partner commercial status ↔ KYC enforcement | **Done (slice 1)** | Partner | `partner_service.set_status()` |
| 17 | Security checklist sign-off | Partial | Ops | [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) |
| 32 | Production Razorpay configuration | Open | Billing | Documented in [DEVELOPMENT.md](./DEVELOPMENT.md); enforced in config |
| 33 | Automated partner payout execution | Open (v1 manual) | Partner/Ops | Workflow shipped; API automation deferred — [PARTNER_PAYOUT.md](./PARTNER_PAYOUT.md) |
| 34 | Automated PostgreSQL backups to S3 | Partial | Ops | `backup_postgres.sh` + systemd timer/cron; enable on host ([PRODUCTION_OPS.md](./PRODUCTION_OPS.md)) |
| 36 | Resume upload malware scanning (ClamAV) | Partial | Security | Hook shipped; enable via `CLAMAV_*` or document waiver in sign-off |
| 37 | Full CSP + security hardening | Partial | Ops | HSTS + CSP-Report-Only; enforce CSP after report review |
| 40 | Production rate limiting (Redis) | Open | Infra | `RATE_LIMIT_STORAGE_URL` must not be `memory` in prod |
| 43 | Full security checklist completion | Open | Ops | Human sign-off |

**Deferred P0 (separate releases):** #22 code signing (full release pipeline).

---

## Phase 2 — P1 product & mock interview

| ID | Item | Status | Workstream | Notes |
|----|------|--------|------------|--------|
| 1 | Published HR contacts on candidate job UI | **Done (slice 1)** | Product | API + Application detail |
| 5 | Mock interview live-stream presenter | POC | Mock interview | Admin `live_stream`; vendor SDK (#44) |
| 7 | Complete report regeneration (vision) | **Done (slice 1)** | Mock interview | Merge prior `presentation` when no new frames |
| 8 | Auto-abandon idle mock sessions | Partial | Mock interview | Beat task + hourly log; verify via [PRODUCTION_OPS.md](./PRODUCTION_OPS.md) |
| 9 | Mock interview live/report frontend tests | **Done (slice 1)** | Tests | Vitest |
| 18 | Partner payout workflow | **Done (slice 3)** | Partner | [PARTNER_PAYOUT.md](./PARTNER_PAYOUT.md); KYC on approve/paid |
| 19 | Company contacts on candidate pages | **Done (slice 1)** | Product | Same as #1 |
| 29 | Regenerate loses vision context | **Done (slice 1)** | Mock interview | `merge_regenerated_feedback()` |
| 30 | Abandoned state needs scheduled task | Partial | Ops | In worker beat; confirm on EC2 with `verify_production_ops.sh` |
| 44 | Commercial talking-avatar SDK | POC | Mock interview | Vendor-dependent |
| 47 | Reliable stale-session cleanup | Partial | Ops | Same as #8/#30; backend test `test_mock_interview_abandon.py` |
| 48 | Vision-aware report regeneration | **Done (slice 1)** | Mock interview | Same as #7/#29 |
| 49 | Live-interview UI regression suite | Partial | Tests | Expanded in slice 1 |
| 51–53 | MI live, report, PDF tests | Partial | Tests | PDF + page smoke in slice 1 |

**Celery beat (ops):** Production must run Celery worker **with beat** so `abandon_stale_mock_interviews` runs hourly (`backend/app/worker.py`). See [DEVELOPMENT.md](./DEVELOPMENT.md#desktop-agent-and-background-tasks).

---

## Phase 3 — P1 agent & auth

| ID | Item | Status | Workstream |
|----|------|--------|------------|
| 3 | Two-factor authentication (2FA/MFA) | **Done (slice 3)** | Auth | TOTP + Settings UI |
| 20 | Agent auto-update (v1.1) | Partial | Agent | `/api/site/agent-release` + startup warning |
| 21 | Agent token in Windows Credential Manager | Partial | Agent | `agent/credentials.py` + keyring |
| 22 | Code signing for Windows agent | Open | Release | Ops / release pipeline |

---

## Phase 4 — P2 & post-launch

| ID | Item | Status | Workstream |
|----|------|--------|------------|
| 2 | LinkedIn job discovery in web app | Not built (non-goal) | Product |
| 4 | Analytics charts / Recharts dashboard | Not built | Product |
| 6 | Photoreal volumetric 3D interviewer | Product choice | Mock interview |
| 10 | MI report PDF tests (extended) | Partial | Tests |
| 11 | Resume Studio frontend tests | Partial | Tests | `ResumesDashboard.test.tsx` smoke |
| 12 | Jobs Dashboard frontend tests | Partial | Tests | `JobsDashboard.test.tsx` smoke |
| 13 | Home Dashboard frontend tests | Partial | Tests | `HomeDashboard.test.tsx` smoke |
| 14 | Agent Connect frontend tests | Partial | Tests | `AgentConnect.test.tsx` smoke |
| 16 | Full mock interview ops metrics dashboard | Partial | Admin | `admin_service.analytics` mock_interviews block |
| 23 | Bundle ChromeDriver with agent | Open | Agent | Selenium Manager shim in engine |
| 24 | Engine `currency` in Easy Apply answers | **Done (slice 3)** | Engine | `config/questions.py` + `append_salary_currency` |
| 25–26 | Deeper engine refactor / ChromeDriver naming | Partial | Engine | Platform-specific driver filename in `open_chrome.py` |
| 27 | Implement or remove `invalidate_caches()` | **Done (slice 3)** | Platform | Short TTL platform row cache |
| 31 | Stripe integration | Partial | Billing | Stub only; production **Razorpay-only** — [BILLING.md](./BILLING.md) |
| 35 | Docker Compose deployment bundle | **Done (slice 3)** | Infra | `docker-compose.yml` + `backend/Dockerfile` |
| 38 | PostgreSQL migration CI (`TEST_POSTGRES_URL`) | Partial | CI | `ci_postgres_migrate.sh` + `.github/workflows/ci.yml` |
| 39 | Live OpenAI integration test | Optional skip | CI | Unchanged |
| 42 | Automated production smoke tests | Partial | Ops | `smoke_production.sh`; runs on deploy via `update_server.sh` |
| 45 | Datadog/CloudWatch MI metrics | Not built | Ops |
| 46 | Photoreal 3D avatar default | Not default | Mock interview |
| 54–60 | Extended test matrix | Open | Tests |

---

## Full index (#1–#60)

| # | Title | P | Phase |
|---|--------|---|-------|
| 1 | Show published HR contacts on candidate job pages | P1 | 2 |
| 2 | LinkedIn job discovery in SPA | P2 | 4 |
| 3 | 2FA/MFA | P1 | 3 |
| 4 | Analytics charts dashboard | P2 | 4 |
| 5 | Mock interview live-stream presenter | P1 | 2 |
| 6 | Photoreal animated 3D interviewer | P2 | 4 |
| 7 | Complete MI report regeneration | P1 | 2 |
| 8 | Auto-abandon idle MI sessions | P1 | 2 |
| 9 | MI live-stage frontend tests | P1 | 2 |
| 10 | MI PDF export tests | P2 | 4 |
| 11 | Resume Studio frontend tests | P2 | 4 |
| 12 | Jobs Dashboard frontend tests | P2 | 4 |
| 13 | Home Dashboard frontend tests | P2 | 4 |
| 14 | Agent Connect frontend tests | P2 | 4 |
| 15 | Partner status ↔ KYC enforcement | P0 | 1 |
| 16 | Full MI ops metrics dashboard | P2 | 4 |
| 17 | Security checklist sign-off | P0 | 1 |
| 18 | Automated partner payouts | P1 | 2 |
| 19 | Company contacts on candidate pages | P1 | 2 |
| 20 | Agent auto-update | P1 | 3 |
| 21 | Credential Manager for agent token | P0 | 3 |
| 22 | Code signing agent EXE | P1 | 3 |
| 23 | Bundle ChromeDriver | P2 | 4 |
| 24 | Engine currency config | P2 | 4 |
| 25 | Deeper engine refactor | P2 | 4 |
| 26 | ChromeDriver platform naming | P2 | 4 |
| 27 | `invalidate_caches()` | Documented stub | 4 | Reserved in `platform_settings_service.py` |
| 28 | Partner KYC branch (same as 15) | P0 | 1 |
| 29 | MI regenerate vision context | P1 | 2 |
| 30 | MI abandoned + Celery beat | P1 | 2 |
| 31 | Stripe | P2 | 4 |
| 32 | Production payment config | P0 | 1 |
| 33 | Partner payouts + Razorpay | P1 | 2 |
| 34 | PG backups to S3 | P0 | 1 |
| 35 | Docker Compose | P2 | 4 |
| 36 | ClamAV resume scan | P0 | 1 |
| 37 | CSP / hardening | P0 | 1 |
| 38 | PG migration CI | P1 | 4 |
| 39 | OpenAI live test | P1 | 4 |
| 40 | Prod rate limits (Redis) | P0 | 1 |
| 41 | SES production readiness | P1 | Ops |
| 42 | Automated deploy smoke | P1 | 4 |
| 43 | Security sign-off | P0 | 1 |
| 44 | Talking-avatar SDK | P1 | 2 |
| 45 | Log metrics dashboard | P2 | 4 |
| 46 | Photoreal 3D default | P2 | 4 |
| 47 | Stale MI session cleanup | P1 | 2 |
| 48 | Vision-aware regenerate | P1 | 2 |
| 49 | MI UI regression suite | P1 | 2 |
| 50 | MI PDF regression (overlap #10) | P2 | 4 |
| 51 | Test MI live stage | P1 | 2 |
| 52 | Test MI report flow | P1 | 2 |
| 53 | Test MI PDF | P2 | 2/4 |
| 54–60 | Dashboard/agent/resume tests, CI, smoke | P1–P2 | 4 |

---

## Partner payout admin workflow (reference)

1. Partner completes KYC (admin sets `kyc_status` to `verified` or `not_required`).
2. Admin sets partner `status` to `approved` / `active` (requires eligible KYC).
3. Commissions accrue on qualifying payments (`partner_service.maybe_accrue_commission`).
4. Partner requests payout; admin approves and marks paid — requires Razorpay and operational process (#18, #33).
