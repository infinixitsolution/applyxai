# ApplyXAI — API Inventory

**Date:** 2026-10-16  
**Base URL (local):** `http://127.0.0.1:8010/api`  
**OpenAPI:** `GET /api/docs` (disabled when `APP_ENV=production`)  
**Registration:** `backend/app/main.py`

All routes below are prefixed with `/api`. Authentication: **`get_current_user`** unless noted. Admin routes use **`require_admin`**.

## Router summary

| Router module | Prefix (after `/api`) | ~Routes | Auth |
|---------------|------------------------|---------|------|
| `health` | `/health` | 1 | Public |
| `auth` | `/auth/*` | 14 | Mixed (login public) |
| `profile` | `/profile`, preferences | 14+ | User |
| `profile_linkedin` | LinkedIn sync | 3 | User |
| `questions` | `/questions` | 4 | User |
| `settings_automation` | `/settings/automation` | 3 | User |
| `resumes` | `/resumes` | 13 | User |
| `jobs` | `/jobs` | 2 | User |
| `applications` | `/applications` | 3+ | User |
| `dashboard` | `/dashboard` | 2 | User |
| `notifications` | `/notifications` | 5 | User |
| `plans` | `/plans` | 1 | User |
| `automation` | `/automation` | 15 | User |
| `agent` | `/agent` | 20 | Device / user |
| `billing` | `/billing` | 5 | User + webhooks |
| `admin` | `/admin` | 64 | Admin |
| `institute` | `/institute` | 15 | Institute role |
| `invites` | `/invites` | (institute) | Mixed |
| `partner` | `/partner` | 15 | Partner role |
| `referrals` | `/referrals` | 1 | User |
| `site` | `/site` | 4 | Mostly public |
| `support` | `/support` | 3 | User |
| `mock_interviews` | `/mock-interviews` | 11 | User |
| `live_interviews` | `/live-interviews` | 5 | User |

**Approximate total route handlers:** ~200 (decorator count across `backend/app/api`).

## Critical workflows → endpoints

| Workflow | Primary endpoints |
|----------|-------------------|
| Register / login | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` |
| Profile CRUD | `GET/PUT /profile`, `PATCH /profile/sections/{section}` |
| Custom questions | `GET/PUT /questions`, `PATCH/DELETE /questions/{id}` |
| Automation settings | `GET/PATCH /settings/automation` |
| Start / control run | `POST /automation/runs`, poll via agent `POST /agent/poll` |
| Ingest events | `POST /agent/runs/{id}/events` |
| Applications list | `GET /applications`, `GET /applications/{id}` |
| Billing | `POST /billing/checkout`, `POST /billing/webhook/razorpay` |
| Health | `GET /health` — includes `automation_poll: resume-idle-v2` marker |

## Test coverage (representative)

| Area | Test module |
|------|-------------|
| Auth | `test_auth_api.py`, `test_two_factor_api.py` |
| Isolation | `test_isolation.py` |
| Automation | `test_automation_api.py`, `test_agent_e2e.py` |
| Billing | `test_billing_api.py` |
| Admin | `test_admin_api.py` |
| Profile | `test_master_profile_api.py`, `test_preferences_api.py` |
| Questions | Covered via preferences / custom questions services |

For per-endpoint OpenAPI schemas, use `/api/docs` against a running dev server.

See [AUDIT.md](./AUDIT.md).
