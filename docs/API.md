# ApplyXAI — API

Base path `/api`. Interactive OpenAPI docs: `/api/docs` (raw schema: `/api/openapi.json`).

## Conventions

Every response uses one envelope:

```json
{ "success": true,  "data": { } }
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "…", "details": [ ] } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Body failed validation; `details` lists `{field, message}` |
| `UNAUTHORIZED` | 401 | Not logged in, or the session was revoked |
| `SESSION_EXPIRED` | 401 | Refresh failed; log in again |
| `INVALID_CREDENTIALS` | 401 | Wrong email or password (same answer for unknown emails) |
| `EMAIL_NOT_VERIFIED` | 403 | Correct password, email not yet verified |
| `ACCOUNT_DISABLED` | 403 | Account deactivated |
| `FORBIDDEN` | 403 | Logged in, but not allowed (e.g. not an admin) |
| `CSRF_FAILED` | 403 | Missing or wrong `X-CSRF-Token` header |
| `INVALID_TOKEN` | 400 | Email link is wrong, used, or expired |
| `WEAK_PASSWORD` | 422 | Password rejected by policy |
| `RATE_LIMITED` | 429 | Too many attempts; see the `Retry-After` header |
| `NOT_FOUND` | 404 | No such route or resource (also used for other users' resources) |
| `INVALID_FILE` | 422 | Upload isn't a real PDF/DOCX, is empty, or its type contradicts its extension |
| `FILE_TOO_LARGE` | 413 | Upload exceeds `MAX_RESUME_BYTES` (5 MB by default) |
| `PLAN_LIMIT_REACHED` | 403 | The user's plan doesn't allow more of this resource |
| `INTERNAL_ERROR` | 500 | Unexpected error; details are only in the server log |

## Authentication model (for frontend developers)

- Login sets three cookies:
  - `applyxai_access`: HttpOnly, 15 minutes, path `/api`. The JWT access token.
  - `applyxai_refresh`: HttpOnly, 30 days, path `/api/auth`. Opaque, rotated on every refresh.
  - `applyxai_csrf`: **readable by JavaScript**, path `/`.
- Send requests with `credentials: "include"`.
- On every `POST`/`PUT`/`PATCH`/`DELETE`, send the header `X-CSRF-Token: <value of the applyxai_csrf cookie>`. The pre-login endpoints (register, login, verify, resend, forgot, reset) don't need it.
- On a `401 UNAUTHORIZED`, call `POST /api/auth/refresh` once and retry. If that fails too, send the user to the login page. Make sure only one refresh runs at a time.

## Auth endpoints

| Method | Path | Body | Success | Notes |
|---|---|---|---|---|
| POST | `/auth/register` | `{email, password, first_name?, last_name?}` | 202 `{message}` | Same response if the email already exists; the owner gets a notice email instead. 10/hour per IP |
| POST | `/auth/verify-email` | `{token}` | 200 `{user}` | Token from the email link, single use, 24h |
| POST | `/auth/resend-verification` | `{email}` | 202 `{message}` | Always 202. 5/hour per IP, 3/hour per email |
| POST | `/auth/login` | `{email, password}` | 200 `{user}` + cookies | 5/minute per IP, 10/hour per email |
| POST | `/auth/refresh` | none (refresh cookie) | 200 `{user}` + new cookies | Reusing an old refresh token revokes all sessions |
| POST | `/auth/logout` | none | 200 | Ends this session, clears cookies |
| POST | `/auth/logout-all` | none | 200 | Ends every session of the user, on every device |
| GET | `/auth/me` | none | 200 `{user}` | |
| POST | `/auth/forgot-password` | `{email}` | 202 `{message}` | Always 202. 5/hour per IP, 3/hour per email |
| POST | `/auth/reset-password` | `{token, new_password}` | 200 | Single use, 60 min; ends all sessions |

Password policy: 10–128 characters, no leading or trailing spaces, at least 4 distinct characters, and not equal to the email address.

`user` object:

```json
{ "id": "uuid", "email": "alice@example.com", "first_name": "Alice", "last_name": "",
  "is_verified": true, "is_admin": false, "created_at": "…", "last_login_at": "…" }
```

## Profile and preferences

All require login and only ever touch the caller's own data.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/profile` | none | `{email, first_name, last_name, phone, headline, summary, current_title, current_company, experience_years, skills, preferred_roles, preferred_locations}` |
| PUT | `/profile` | same fields minus `email` | Full replace. Lists are trimmed and de-duplicated; unknown fields are rejected |
| GET | `/preferences/options` | none | Allowed values for every option field, plus form metadata (`key, label, type, help, options`) for the extra search settings and application answers |
| GET | `/preferences/search` | none | Saved search, or the defaults with `"configured": false` |
| PUT | `/preferences/search` | see below | Full replace |
| GET | `/preferences/application` | none | `{answers, human_questions, ai_applications_enabled, user_information_all, ai_policy, ai_available}` |
| PATCH | `/preferences/application` | partial | Engine keys merge into `answers` (`null` removes a key); QA keys replace when sent |

Search body:

```json
{ "keywords": ["Python Developer"], "location": "Bengaluru, India", "easy_apply_only": true,
  "experience_level": ["Entry level", "Associate"], "job_type": ["Full-time"], "on_site": ["Remote", "Hybrid"],
  "companies": [], "date_posted": "Past week", "sort_by": "Most recent",
  "salary_min": 500000, "salary_max": 1500000,
  "extra": { "current_experience": 3, "bad_words": ["unpaid"] } }
```

Option values are the exact strings the automation engine uses (it clicks LinkedIn filters by their visible text), so they're case-sensitive and never numeric codes. `["1"]`, `"entry level"`, or `"permanent"` get `422 VALIDATION_ERROR`. The lists are in `automation/options.py`, and a test keeps them identical to `modules/validator.py`.

| Field | Allowed values |
|---|---|
| `experience_level` | Internship, Entry level, Associate, Mid-Senior level, Director, Executive |
| `job_type` | Full-time, Part-time, Contract, Temporary, Volunteer, Internship, Other |
| `on_site` | On-site, Remote, Hybrid |
| `date_posted` | `""`, Any time, Past month, Past week, Past 24 hours |
| `sort_by` | `""`, Most recent, Most relevant |

`extra` and the application answers accept only the engine settings listed by `/preferences/options`, type-checked the way the engine checks them (for example `desired_salary` must be a whole number ≥ 0, and `switch_number` ≥ 1). Account secrets (LinkedIn username/password, AI API keys) are never accepted.

## Resumes

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/resumes` | none | `{resumes: [...], limit}`; default first |
| POST | `/resumes` | multipart: `file`, optional `name` | 201. PDF or DOCX only, max 5 MB, checked by content, not just the extension. The first resume becomes the default. 30/hour |
| PATCH | `/resumes/{id}` | `{name}` | Rename |
| POST | `/resumes/{id}/default` | none | Make default (exactly one per user) |
| DELETE | `/resumes/{id}` | none | Deleting the default promotes the newest remaining resume |
| GET | `/resumes/{id}/download` | none | The file, as an attachment |
| POST | `/resumes/{id}/analyze-master` | none | Parse upload + profile skills into `master_skills` |
| PATCH | `/resumes/{id}/master-skills` | `{master_skills: string[]}` | Confirm master list (locked during AI tailor) |
| POST | `/resumes/ai/preview` | `{resume_id, job_description}` | Match score, 60% gate, optional tailor patch (no save) |
| POST | `/resumes/ai/tailor` | `{resume_id, job_description, job_id?}` | 201; saves new DOCX when gate passes. 20/hour |

Resume object: `{id, name, filename, file_type, file_size, is_default, created_at}`. `filename` is the sanitised upload name, for display only.

## Lists and pagination

List endpoints take `page` (default 1) and `page_size` (default 20, max 100) and return:

```json
{ "items": [ ], "total": 42, "page": 1, "page_size": 20 }
```

All timestamps are ISO 8601 in UTC with an offset (`2026-10-07T03:30:00+00:00`).

## Applications and jobs

Applications and jobs are created by the automation worker, never by the browser, so these endpoints are read-only.

| Method | Path | Notes |
|---|---|---|
| GET | `/applications` | Filters: `status` (repeatable), `q` (title/company/location), `company`, `applied_from`/`applied_to` (YYYY-MM-DD, UTC, inclusive), `automation_job_id`. `sort`: `created_at`, `applied_at`, `updated_at`, `company`, `title`, with `-` for descending (default `-created_at`) |
| GET | `/applications/export` | The same filters, as a CSV attachment (max 10,000 rows, 20/hour). Cells starting with `= + - @` are prefixed with `'` so spreadsheets don't run them as formulas |
| GET | `/applications/{id}` | Includes the full job description |
| GET | `/jobs` | Jobs your automation has encountered, newest first, each with your `application` (`id, status, applied_at`). Filters: `q`, `company`, `work_setting` |
| GET | `/jobs/{id}` | 404 unless you have an application for it |

Application statuses: `discovered`, `queued`, `running`, `applied`, `failed`, `skipped`, `external`, `cancelled`.

Application object: `{id, status, applied_at, failure_reason, resume_id, automation_job_id, created_at, updated_at, job: {id, platform, external_id, title, company, location, job_url, work_setting, employment_type, experience_level, salary_min, salary_max, discovered_at}}`.

## Dashboard and usage

| Method | Path | Notes |
|---|---|---|
| GET | `/dashboard/stats` | See below |
| GET | `/usage` | `{plan, plan_name, period, resets_at, applications: {used, limit, remaining}, resumes: {...}, jobs_discovered, runtime_seconds, limit_reached}` |

`/dashboard/stats` returns:
- `applications_by_status` (all-time counts), `total_applied`, `applied_today`
- `success_rate`: applied ÷ (applied + failed), or `null` with no attempts yet
- `daily`: the last 30 UTC days as `{date, applied, failed}`
- `top_companies`: up to 5 `{company, applied}`
- `recent_applications`: 5 application objects
- `automation`: `{active, last}`, each a run summary or `null`
- `usage`: the same object as `/usage`

Usage resets on the first of each month (UTC). Only the first successful submission for a job counts toward the monthly limit.

## Notifications

| Method | Path | Notes |
|---|---|---|
| GET | `/notifications` | Newest first; `unread_only=true` to filter. The response also has `unread_count` |
| POST | `/notifications/{id}/read` | Mark one as read |
| POST | `/notifications/read-all` | Returns `{marked}` |

Notification object: `{id, type, title, body, link, read_at, created_at}`. `link` is always an in-app path (for example `/automation`).

## Automation

For the logged-in user (cookie session, CSRF on POST/DELETE). How runs execute is described in `docs/AUTOMATION.md`.

| Method | Path | Notes |
|---|---|---|
| GET | `/automation` | `{active, recent, devices, agent_online, readiness, usage}`. `readiness` is `{ready, problems}`, where `problems` lists in plain language what must be done before a run can start |
| POST | `/automation/start` | Body `{dry_run: false}`. Creates a queued run. Errors: `NOT_READY` 422 (`details.problems`), `PLAN_LIMIT_REACHED` 403, `NO_AGENT` 409 (no connected computer), `RUN_ACTIVE` 409. 30/hour |
| GET | `/automation/{id}` | Run object |
| GET | `/automation/{id}/logs` | `?after=<seq>&limit=<=500`. `{items: [{seq, ts, level, event, message}], next_after}`; poll with `after=next_after` |
| POST | `/automation/{id}/pause` | Takes effect between jobs. `RUN_FINISHED`, `RUN_NOT_STARTED`, or `RUN_STOPPING` 409 when it can't |
| POST | `/automation/{id}/resume` | |
| POST | `/automation/{id}/stop` | A run no computer has picked up yet is cancelled at once; otherwise it stops after the current job |
| GET | `/automation/devices` | Connected computers: `[{id, name, platform, agent_version, paired_at, last_seen_at, online}]` |
| POST | `/automation/devices/pairing-code` | `{code: "ABCD-2345", expires_at}`. Valid 10 minutes, single use; a new code voids the previous one. `DEVICE_LIMIT_REACHED` 409 at 5 computers. 10/hour |
| DELETE | `/automation/devices/{id}` | Disconnects the computer immediately |

Run object: `{id, status, control, dry_run, created_at, started_at, finished_at, current_job, total_jobs, successful_count, failed_count, skipped_count, error_message, stop_reason, claimed}`. `status` ∈ queued, running, paused, completed, failed, cancelled; `control` ∈ run, pause, stop; `stop_reason` ∈ "", user, plan_limit.

## Desktop agent

Called only by the agent (`python -m agent`). It authenticates with `Authorization: Bearer axd_...`, never cookies, so CSRF doesn't apply. A missing, revoked, or unknown token returns 401 `DEVICE_UNAUTHORIZED`.

| Method | Path | Notes |
|---|---|---|
| POST | `/agent/pair` | No auth. Body `{code, name, platform, agent_version}`. Returns `{token, device_id, user_id, name}`; the token is shown once. `INVALID_PAIRING_CODE` 400. 10/minute and 50/hour per IP |
| GET | `/agent/me` | This computer, as in `/automation/devices`. Never hands out a run |
| POST | `/agent/unpair` | Revokes this token. `{revoked: true}` |
| POST | `/agent/poll` | Body `{active_run_id, platform, agent_version}`. Returns `{run, user_id}`; `run` is null when there's nothing to do, otherwise `{id, dry_run, control, next_seq, values, resume, remaining_applications, application_qa, ai_available, resume_mode}`. A held run that isn't reported as active is marked failed |
| GET | `/agent/runs/{id}/resume` | The run's default resume file, only while the run is active |
| POST | `/agent/runs/{id}/ai/answer` | Body `{question, question_type, options?, job_description?, job_title?, company?}`. Platform AI draft for an application question; requires user AI toggle and admin AI. Returns `{answer}`. 60/minute per device |
| POST | `/agent/runs/{id}/events` | Body `{first_seq, events}` (at most 200). Returns `{next_seq, control, status, remaining_applications}`. `SEQUENCE_GAP` 409 with `details.next_seq` |

## Billing

For the logged-in user (cookie session, CSRF on POST). Plans and prices come from the `plans` table (seeded from `backend/app/core/plans.py`); the browser never sends a price or a payment status the server trusts.

| Method | Path | Notes |
|---|---|---|
| GET | `/billing` | `{provider, subscription, pending, usage, payments}`. `subscription` is the paid plan in force (null on Free); `pending` is a checkout started in the last hour that the provider hasn't activated yet; `payments` are the 24 most recent |
| POST | `/billing/checkout` | Body `{plan}`. Creates a provider subscription and returns `{subscription, checkout, replaces}`. `checkout` holds what Razorpay Checkout needs (`key`, `subscription_id`, `name`, `description`, `prefill`); it's null with the development provider, which activates the plan at once. `replaces` is the plan that ends when this one activates. Errors: `FREE_PLAN` 400, `PLAN_NOT_FOUND` 404, `ALREADY_SUBSCRIBED` 409, `PLAN_NOT_AVAILABLE` 503 (plan not created at Razorpay yet). 20/hour |
| POST | `/billing/confirm` | Body `{payment_id, subscription_id, signature}` from Razorpay Checkout. The signature is checked, then the subscription and payment are fetched from Razorpay; only that decides the status. `INVALID_PAYMENT_SIGNATURE` 400; another user's subscription is 404. 30/hour |
| POST | `/billing/cancel` | Cancels at the end of the paid period (`cancel_at_period_end: true`). `NO_SUBSCRIPTION` 404 on Free; `COMPLIMENTARY_PLAN` 409 for a plan an admin gave (it ends by itself). Repeating it is harmless |
| POST | `/billing/webhook/razorpay` | Razorpay only (no session). See below |

Subscription object: `{id, plan: {code, name, price_cents, currency, interval}, status, provider, current_period_start, current_period_end, cancel_at_period_end, created_at}`. `status` ∈ pending, trialing, active, past_due, cancelled, expired. Payment object: `{id, amount_cents, currency, status, method, description, paid_at}`; amounts are in the currency's minor unit (paise).

Switching to another paid plan starts a new subscription; when it activates, the previous one is cancelled at Razorpay immediately, with no refund for unused days. A failed renewal (`past_due`) drops the user to Free limits until a payment succeeds.

**Webhook.** Configure it in the Razorpay Dashboard for the `subscription.*` events (at least activated, charged, pending, halted, cancelled, completed). The `X-Razorpay-Signature` header must be the HMAC-SHA256 of the raw body with `PAYMENT_WEBHOOK_SECRET`, or the request is refused with 400 `INVALID_SIGNATURE`. Each `X-Razorpay-Event-Id` is processed once (`{"duplicate": true}` on redelivery). The payload only signals that something changed: the subscription's current state is always re-read from Razorpay's API, so events arriving out of order can't move it backwards. If Razorpay can't be reached, the webhook answers 502 and nothing is recorded, so Razorpay retries it.

## Other endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness + database check; 503 `DATABASE_UNAVAILABLE` if the DB is down |
| GET | `/site/public` | Public. `{branding, banner, landing, legal}` for the marketing site (no auth) |
| GET | `/plans` | Public. Active plans for the pricing page: `[{code, name, price_cents, currency, interval, limits: {applications_per_month, resumes}}]`. Falls back to `backend/app/core/plans.py` when the `plans` table is empty |

## Admin

Every route under `/admin` needs a session whose user has `is_admin`; anyone else gets 403 `FORBIDDEN` (401 without a session). Lists take `page` and `page_size` and return the usual page object. Every change is written to the admin audit log.

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/analytics` | `{users: {total, active, verified, admins, new_7d, new_30d, active_30d}, subscriptions: {by_plan, mrr_cents, past_due}, revenue_30d_cents, applications: {this_month_by_status, daily}, automation: {active_runs, last_24h_by_status, devices, devices_online}}`. Money is keyed by currency. `mrr_cents` counts only paid plans that will renew (complimentary and cancelled plans are left out) |
| GET | `/admin/users` | Filters: `q` (email or name), `status` (active, disabled, admin, unverified), `plan` (plan code; `free` means no paid or complimentary plan). Each row: account flags, `plan`, `plan_name`, `applications_this_month` |
| GET | `/admin/users/{id}` | `{user, usage, subscription, subscriptions, payments, runs, devices, applications_by_status, resumes}`. Never resume files, form answers, or card details |
| PATCH | `/admin/users/{id}` | Body `{is_active?, is_admin?}`. Disabling signs the user out everywhere, disconnects their desktop agents, and stops a run in progress (`stop_reason: admin`). `CANNOT_CHANGE_SELF` 400 for disabling yourself or removing your own admin access |
| POST | `/admin/users/{id}/grant-plan` | Body `{plan, months (1-24), note}`. A complimentary plan (`provider: "admin"`), with no payment, that ends by itself; it replaces an earlier grant. `FREE_PLAN` 400, `PLAN_NOT_FOUND` 404, `HAS_SUBSCRIPTION` 409 while the user pays for a plan. The user can't cancel it (`COMPLIMENTARY_PLAN` 409 on `/billing/cancel`); buying a plan ends it |
| POST | `/admin/users/{id}/revoke-plan` | Ends the complimentary plan now. `NO_GRANT` 404 |
| GET | `/admin/subscriptions` | Filters: `status`, `plan`. Subscription objects plus `user_id`, `user_email` |
| GET | `/admin/automation-jobs` | Filter: `status` (a run status, or `active` for queued/running/paused). Run objects plus `user_id`, `user_email`, `device` |
| POST | `/admin/automation-jobs/{id}/stop` | Stops the run after its current job; the user sees "stopped by ApplyXAI support". `RUN_FINISHED` 409 if it already ended |
| GET | `/admin/applications` | Filters: `status`, `q` (title, company, or user email) |
| GET | `/admin/logs` | Automation log lines from all runs. `level` can repeat (`?level=error&level=warning`, the default); `q` searches messages |
| GET | `/admin/audit-log` | `{id, created_at, admin_email, action, target, target_user_id, details}`, newest first. Actions include `user.update`, `user.verify`, `user.resend_verification`, `plan.grant`, `plan.revoke`, `plan.update`, `run.stop`, `email.test`, `settings.cms`, `settings.smtp`, `settings.auth_email`, `settings.notifications` |
| GET | `/admin/workers` | `{celery: {broker: ok or unreachable, workers}, devices}`. Never fails when Redis is down |
| GET | `/admin/settings` | `{cms, smtp, auth_email, notifications, infrastructure, unverified_users}`. SMTP never includes the password; `smtp.password_configured` is boolean |
| PUT | `/admin/settings/cms` | Full CMS document (branding, banner, landing, legal markdown). 30/hour per admin |
| PUT | `/admin/settings/smtp` | `{enabled, host, port, username, password?, from_address}`. Empty `password` keeps the stored password; empty `host` clears DB SMTP and falls back to `.env` |
| PUT | `/admin/settings/auth-email` | `{require_verification, verification_hours, password_reset_minutes, frontend_url}` |
| PUT | `/admin/settings/notifications` | `{types: {event_type: {email: bool}}}` for known event types only |
| PUT | `/admin/settings/payments` | `{provider: null\|razorpay, key_id, key_secret?, webhook_secret?}`. Secrets encrypted; never returned. Overrides `.env` when `key_id` is saved here |
| POST | `/admin/settings/payments/test` | Validates Razorpay Key ID + secret against the API |
| POST | `/admin/settings/payments/sync-plans` | Creates paid plans at Razorpay (same as `python -m backend.app.cli sync-plans`) |
| PUT | `/admin/settings/ai` | `{enabled, provider, base_url, api_key?, models: {fast, strong, embedding}, features: {applications, resume}}`. API key encrypted; never returned. Configure before enabling user AI toggles in production |
| POST | `/admin/settings/ai/test` | Smoke-test chat with the configured provider |
| GET | `/admin/email` | Legacy summary; prefer `/admin/settings`. `{mode, host, port, …, unverified_users}` |
| POST | `/admin/email/test` | Body `{to?}` (defaults to the admin's address). Sends right away and returns `{delivered, mode, error}`; `error` is the mail server's reason when it refuses. 10/hour per admin |
| POST | `/admin/users/{id}/verify-email` | Marks the address verified and voids outstanding verification links. `ALREADY_VERIFIED` 409 |
| POST | `/admin/users/{id}/resend-verification` | Emails a new verification link; earlier links stop working. `ALREADY_VERIFIED` 409, `ACCOUNT_DISABLED` 409 |
| GET | `/admin/plans` | Every plan, including hidden ones, with `limits`, `is_active`, `sort_order`, `provider_plan_id`, `subscribers` |
| PUT | `/admin/plans/{code}` | Body `{name, price_cents, applications_per_month, resumes, is_active, sort_order}`. Limits apply at once to everyone on the plan. A new price creates a new Razorpay plan for new subscribers; existing subscribers keep paying the old price. Paid plans cost at least 100 minor units; the Free plan must stay free and on sale (`INVALID_PRICE`, `CANNOT_DISABLE_FREE` 422) |
