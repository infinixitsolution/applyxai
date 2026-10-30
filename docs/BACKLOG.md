# ApplyXAI — Product backlog

**Canonical tracker** for incomplete features, partial implementations, tests, and production readiness.  
**Last updated:** 2026-10-24 (leftovers close-out: GST, Stripe Checkout, RazorpayX, candidate referrals, institute outreach, WhatsApp Cloud, Desktop updater/ChromeDriver).

Related docs: [PENDING_PARTIAL_WORK.md](./PENDING_PARTIAL_WORK.md) (open + partial inventory), [MOCK_INTERVIEW_IMPLEMENTATION_PLAN.md](./MOCK_INTERVIEW_IMPLEMENTATION_PLAN.md) (mock interview WPs done), [INSTITUTE_OUTREACH.md](./INSTITUTE_OUTREACH.md), [P0_LAUNCH_CHECKLIST.md](./P0_LAUNCH_CHECKLIST.md) (launch-only tracker), [SITE_AUDIT.md](./SITE_AUDIT.md) (deploy smoke), [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) (agent + sign-off), [SAAS_ROADMAP.md](./SAAS_ROADMAP.md) (historical architecture proposal).

## Architecture non-goals

- **Server-side Chrome / browser farms** (SaaS roadmap Option B): not planned. Job discovery and Easy Apply run on the **user’s desktop agent** ([AUTOMATION.md](./AUTOMATION.md)).
- **LinkedIn job discovery inside the SPA** (#2): same as above unless product explicitly changes execution model.

## Intentional — not defects

| Item | Location | Notes |
|------|----------|--------|
| `NullProvider` / `NOT_SUPPORTED` | `backend/app/services/payments/null.py` | Expected when payments disabled in dev |
| JSON parse `pass` in mock interview parsers | `mock_interview_service.py` | Fall-through to repair/retry |
| `except OSError: pass` on temp file delete | `resume_service.py` | Best-effort cleanup |
| Stripe without keys | `stripe_provider.py` | Checkout Sessions ship; blocked until Admin Payments has Stripe keys |

---

## Phase 1 — P0 launch blockers

| ID | Item | Status | Workstream | Notes |
|----|------|--------|------------|--------|
| 15 | Partner commercial status ↔ KYC enforcement | **Done (slice 1)** | Partner | `partner_service.set_status()` |
| 17 | Security checklist sign-off | Partial | Ops | [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) |
| 32 | Production Razorpay configuration | Open | Billing | Documented in [DEVELOPMENT.md](./DEVELOPMENT.md); enforced in config |
| 33 | Automated partner payout execution | **Done (RazorpayX + manual fallback)** | Partner/Ops | Pay now via RazorpayX; else bank transfer id then Mark paid — [PARTNER_PAYOUT.md](./PARTNER_PAYOUT.md) |
| 34 | Automated PostgreSQL backups to S3 | Partial | Ops | `backup_postgres.sh` + systemd timer/cron; enable on host ([PRODUCTION_OPS.md](./PRODUCTION_OPS.md)) |
| 36 | Resume upload malware scanning (ClamAV) | Partial | Security | Hook shipped; enable via `CLAMAV_*` or document waiver in sign-off |
| 37 | Full CSP + security hardening | **Done in repo** | Ops | Enforced CSP in nginx snippet (Razorpay + Stripe); deploy on host |
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
| 8 | Auto-abandon idle mock sessions | **Done in code** | Mock interview | Beat task + hourly log; confirm on host via [PRODUCTION_OPS.md](./PRODUCTION_OPS.md) |
| 9 | Mock interview live/report frontend tests | **Done (slice 1)** | Tests | Vitest |
| 18 | Partner payout workflow | **Done (slice 3)** | Partner | [PARTNER_PAYOUT.md](./PARTNER_PAYOUT.md); KYC on approve/paid |
| 19 | Company contacts on candidate pages | **Done (slice 1)** | Product | Same as #1 |
| 29 | Regenerate loses vision context | **Done (slice 1)** | Mock interview | `merge_regenerated_feedback()` |
| 30 | Abandoned state needs scheduled task | **Done in code** | Ops | In worker beat; confirm on EC2 with `verify_production_ops.sh` |
| 44 | Commercial talking-avatar SDK | POC | Mock interview | Vendor-dependent |
| 47 | Reliable stale-session cleanup | **Done in code** | Ops | Same as #8/#30; backend test `test_mock_interview_abandon.py` |
| 48 | Vision-aware report regeneration | **Done (slice 1)** | Mock interview | Same as #7/#29 |
| 49 | Live-interview UI regression suite | **Done (slice 2)** | Tests | Live flow + live PDF smokes |
| 51–53 | MI live, report, PDF tests | **Done (slice 2)** | Tests | Live stage, live_stream presenter, PDF smokes |

**Celery beat (ops):** Production must run Celery worker **with beat** so `abandon_stale_mock_interviews` runs hourly (`backend/app/worker.py`). See [DEVELOPMENT.md](./DEVELOPMENT.md#desktop-agent-and-background-tasks).

---

## Phase 2b — P1 institute outreach (admin)

| ID | Item | Status | Workstream | Notes |
|----|------|--------|------------|--------|
| 61 | Scrape + campaign rotation (Firecrawl) | **Done (slice 1)** | Outreach | `institute_scrape_service`, admin Scrape page, Celery `outreach_automation_tick` |
| 62 | Lead profile complete → 100% gate → proposal → send | **Done (slice 1)** | Outreach | `institute_outreach_service`, automation tick throttling |
| 63 | Bulk import / bulk complete / bulk AI enhance | **Done (slice 1)** | Outreach | `bulk_import_leads`, `bulk_leads_action`, Leads UI |
| 64 | WhatsApp Web bridge (link, send, test) | **Done (slice 1)** | Outreach | `whatsapp-bridge/`, admin WhatsApp page; unofficial Web client |
| 65 | Admin WhatsApp chat (inbound webhook + threads + reply) | **Done (slice 1)** | Outreach | `internal_outreach`, `institute_outreach_chat_service`, `/admin/outreach/chat` |
| 66 | Chat sync from bridge + attachments | **Done (slice)** | Outreach | Bridge sync + Cloud media send; live Chrome session still ops |
| 67 | Meta WhatsApp Business Cloud API | **Done (needs WABA)** | Outreach | Cloud provider beside unofficial bridge — [INSTITUTE_OUTREACH.md](./INSTITUTE_OUTREACH.md) |
| 68 | Institute portal outreach / chat (self-service) | **Done (slice 1)** | Outreach | `/api/institute/outreach/*` scoped by `owner_institute_id` |
| 69 | Social scrape beyond public URL search | Partial | Outreach | Facebook / Instagram / LinkedIn — search hits only, no logged-in scrape |
| 70 | Outreach E2E in CI (bridge mocked) | **Done (mocked)** | Tests | Named CI step; no live Firecrawl |

**Ops dependency:** Outreach automation needs Celery **worker + beat**, `OUTREACH_AUTOMATION_ENABLED`, Firecrawl + platform AI, SMTP, and WhatsApp bridge on the API host (`WHATSAPP_BRIDGE_SECRET`, `scripts/start_whatsapp_bridge.ps1`).

---

## Phase 3 — P1 agent & auth

| ID | Item | Status | Workstream |
|----|------|--------|------------|
| 3 | Two-factor authentication (2FA/MFA) | **Done (slice 3)** | Auth | TOTP + Settings UI |
| 20 | Agent auto-update (v1.1) | **Done (slice)** | Agent | Desktop prompts, downloads NSIS from `/api/site/agent-release`, launches installer, quits |
| 21 | Agent token in Windows Credential Manager | **Done (slice)** | Agent | `agent/credentials.py` + keyring; JSON fallback if the OS store fails |
| 22 | Code signing for Windows agent | Partial | Release | `CSC_LINK` / `electron-builder.yml`; unsigned until you supply the cert |

---

## Phase 4 — P2 & post-launch

| ID | Item | Status | Workstream |
|----|------|--------|------------|
| 2 | LinkedIn job discovery in web app | Not built (non-goal) | Product |
| 4 | Analytics charts / Recharts dashboard | **Done (slice 1)** | Product | Admin Overview DailyChart for sign-ups, applications, revenue |
| 6 | Photoreal volumetric 3D interviewer | Product choice | Mock interview |
| 10 | MI report PDF tests (extended) | **Done (slice 2)** | Tests | Mock + live PDF smokes |
| 11 | Resume Studio frontend tests | **Done (slice 2)** | Tests | List + make-default |
| 12 | Jobs Dashboard frontend tests | **Done (slice 2)** | Tests | List + open details |
| 13 | Home Dashboard frontend tests | **Done (slice 2)** | Tests | Stats + report links |
| 14 | Agent Connect frontend tests | **Done (slice 2)** | Tests | Invalid link + approve session |
| 16 | Full mock interview ops metrics dashboard | **Done (slice)** | Admin | Overview totals, abandoned, avg score, 30-day chart, live-interview block |
| 23 | Bundle ChromeDriver with agent | **Done (slice 1)** | Agent | Pinned Windows x64 in `vendor/` + worker extraResources |
| 24 | Engine `currency` in Easy Apply answers | **Done (slice 3)** | Engine | `config/questions.py` + `append_salary_currency` |
| 25 | Deeper engine refactor | Partial | Engine | `runAiBot.py` still central; not in this close-out |
| 26 | ChromeDriver platform naming | **Done (slice)** | Engine | `chromedriver-win64.exe` pin + platform candidate names |
| 27 | Implement or remove `invalidate_caches()` | **Done (slice 3)** | Platform | Short TTL platform row cache |
| 31 | Stripe integration | **Done (needs keys)** | Billing | Checkout Sessions + webhooks; Razorpay remains the live default — [BILLING.md](./BILLING.md) |
| 35 | Docker Compose deployment bundle | **Done (slice 3)** | Infra | `docker-compose.yml` + `backend/Dockerfile` |
| 38 | PostgreSQL migration CI (`TEST_POSTGRES_URL`) | Partial | CI | `ci_postgres_migrate.sh` + `.github/workflows/ci.yml` |
| 39 | Live OpenAI integration test | Optional skip | CI | Unchanged |
| 42 | Automated production smoke tests | **Done (slice)** | Ops | `smoke_production.sh` fails deploy in `update_server.sh` |
| 45 | Datadog/CloudWatch MI metrics | Not built | Ops |
| 46 | Photoreal 3D avatar default | Not default | Mock interview |
| 54–60 | Extended test matrix | **Partial** | Tests | Dashboard/MI smokes + engine packaging CI job; full `tests/` still not in GitHub Actions |
| 61–70 | Institute outreach (admin) | Mixed | Outreach | See Phase 2b |

---

## Full index (#1–#70)

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
| 41 | Email deliverability (Hostinger SMTP, SPF/DKIM) | P1 | Ops |
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
| 61 | Outreach scrape + campaign | P1 | 2b |
| 62 | Outreach pipeline send gates | P1 | 2b |
| 63 | Bulk lead import / actions | P1 | 2b |
| 64 | WhatsApp Web bridge | P1 | 2b |
| 65 | Admin WhatsApp chat | P1 | 2b |
| 66 | Chat sync + attachments | P1 | 2b |
| 67 | Meta WhatsApp Cloud API | P1 | 2b |
| 68 | Institute portal chat | P1 | 2b |
| 69 | Social source scrape depth | P2 | 2b |
| 70 | Outreach tests in CI | P2 | 2b |

---

## Partner payout admin workflow (reference)

1. Partner completes KYC (admin sets `kyc_status` to `verified` or `not_required`).
2. Admin sets partner `status` to `approved` / `active` (requires eligible KYC).
3. Commissions accrue on qualifying payments (`partner_service.maybe_accrue_commission`).
4. Partner requests payout; admin approves and **Pay now** (RazorpayX) or records a bank transfer id then **Mark paid** (#18, #33).
