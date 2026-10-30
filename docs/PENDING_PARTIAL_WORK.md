# Pending & partial work — entire project

**As of:** 2026-10-24  
**Canonical trackers:** [BACKLOG.md](./BACKLOG.md) · [P0_LAUNCH_CHECKLIST.md](./P0_LAUNCH_CHECKLIST.md) · [AUDIT_FINDINGS.md](./AUDIT_FINDINGS.md) · [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md) · [PRODUCTION_OPS.md](./PRODUCTION_OPS.md)

Campus **institute_managed** billing stays institute-pays (by design). Candidate `/r/` referrals are separate from partner campus commissions.

---

## A. Production launch (P0) — still ops, not code

| ID | Item | Status |
|----|------|--------|
| #17, #43 | Security checklist human sign-off | **Open** — fill [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) |
| #32 | Production Razorpay (live keys, webhooks, reconciliation) | **Open** — you supply live keys |
| #34 | PostgreSQL backups to S3 + tested restore | **Partial** (scripts exist; enable on host) |
| #36 | ClamAV resume scanning | **Partial** (`CLAMAV_*` or waiver in sign-off) |
| #37 | CSP enforcement | **Done in repo** — deploy nginx snippet on host |
| #40 | Redis-backed rate limits in production | **Open** (`RATE_LIMIT_STORAGE_URL` ≠ memory) |
| #22 | Code signing (agent/desktop installers) | **Partial** (`CSC_LINK` wired; unsigned until you supply the cert) |
| #38 | PG migration CI | **Partial** — needs GitHub secret `TEST_POSTGRES_URL` |
| #41 | Email SPF/DKIM/DMARC | **P1 ops** — DNS at Hostinger |
| #8, #30, #47 | Auto-abandon idle mock sessions | **Done in code** — confirm Celery beat on EC2 |

**Not a code gap:** dev uses `PAYMENT_PROVIDER=null` ([AUD-010](./AUDIT_FINDINGS.md) — by design).

Optional vendors (code shipped): Stripe keys (#31), RazorpayX account (#33), Meta WABA (#67).

---

## B. Closed in leftovers + remaining-partial close-out (2026-10-24)

| Area | Backlog | Notes |
|------|---------|--------|
| Master Profile accomplishments | — | Awards, publications, links, notes; completion weight 8 (always ok); mapped into engine answers |
| Naukri job source | — | Default **on** in `DEFAULT_JOB_SOURCES`; alembic 0040 flips stored JSON; Desktop still logs in locally |
| Outreach scrape-job detail UI | — | Admin Scrape drawer calls `GET /scrape-jobs/{id}` |
| Admin analytics charts | #4 | Overview DailyChart for sign-ups, applications, revenue |
| MI ops metrics dashboard | #16 | Totals, abandoned, avg score, 30-day chart, live-interview block |
| Mid-run profile pull | — | Poll heartbeat timestamps; refresh applied at next job checkpoint |
| Playwright smokes | — | `frontend/e2e/smoke.spec.ts` — login, Home, Applications, Jobs, Automation |
| LinkedIn recruiter Connect | — | Default **off**; Automation settings toggle + warning |
| GST on payment | — | Webhook issues invoice, PDF, email |
| Stripe SaaS checkout | #31 | Checkout Sessions + webhooks; needs Stripe keys |
| Partner Pay now | #33 | RazorpayX with manual bank-transfer fallback |
| Candidate-to-candidate referrals | — | `C…` codes, `/r/` cookie `ax_cand_ref`, Settings share UI |
| Bundled ChromeDriver | #23, #26 | `vendor/chromedriver-win64.exe` pin + worker extraResources |
| Desktop auto-update | #20 | Download NSIS from `/api/site/agent-release`, launch, quit |
| Agent Credential Manager | #21 | keyring / keytar; JSON fallback if the OS store fails |
| Institute self-serve outreach | #68 | `/api/institute/outreach/*` + portal pages |
| Meta WhatsApp Cloud | #67, #66 | Text + media send; needs WABA. Bridge stays for local/dev |
| Deploy smoke | #42 | `smoke_production.sh` fails deploy |
| Dashboard / MI Vitest | #11–14, #10, #49, #51–53 | Interaction smokes + live stage / live PDF |
| Outreach mocked CI | #70 | Named pytest step; no live Firecrawl |

**Still non-goals:** server-side Chrome / job discovery in the SPA (#2); photoreal interviewer SDK; Datadog mock-interview metrics.

---

## C. Remaining (not closable in app code alone)

### C.1 Product choice / POC

| ID | Item | Status |
|----|------|--------|
| #5, #44 | Live-stream presenter / talking-avatar SDK | **POC** — iframe/video URL only |
| #69 | Social sources (FB/IG/LinkedIn) | **Partial** — public URL search only |
| #25 | Deeper engine refactor | **Partial** — `runAiBot.py` still central |
| #2 | LinkedIn discovery in SPA | **Non-goal** |
| #6, #46 | Photoreal 3D interviewer default | Product choice |
| #45 | Datadog/CloudWatch MI metrics | Not built |

### C.2 Test matrix leftover

| ID | Item | Status |
|----|------|--------|
| #54–60 | Full engine `tests/` in GitHub Actions | **Partial** — packaging + credentials job only |

---

## D. Quality & test debt

| ID | Issue | Status (2026-10-24) |
|----|--------|---------------------|
| AUD-002 | Engine `human_type` test | **Closed** |
| AUD-011–013 | Isolated engine clusters | **Closed** (pass on re-run) |
| AUD-014 | `tests/test_packaging.py` | **Closed** — import + keyring-isolated round trip |
| — | Playwright smokes | **Shipped** — skip without `E2E_EMAIL` |

---

## E. Priority summary

1. **Before public launch:** Section A (P0) — you supply Razorpay live, Redis, ClamAV or waiver, backups, SPF/DKIM, sign-off.
2. **Optional vendors:** Stripe keys, RazorpayX, Meta WABA, Authenticode cert.
3. **Detail per item:** [BACKLOG.md](./BACKLOG.md) full index #1–#70.
