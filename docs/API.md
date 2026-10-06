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
| GET | `/preferences/application` | none | `{engine_setting: value}`; only keys the user has set |
| PATCH | `/preferences/application` | `{engine_setting: value \| null}` | Merges; `null` removes a key so the engine default applies |

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
| POST | `/agent/poll` | Body `{active_run_id, platform, agent_version}`. Returns `{run, user_id}`; `run` is null when there's nothing to do, otherwise `{id, dry_run, control, next_seq, values, resume, remaining_applications}`. A held run that isn't reported as active is marked failed |
| GET | `/agent/runs/{id}/resume` | The run's default resume file, only while the run is active |
| POST | `/agent/runs/{id}/events` | Body `{first_seq, events}` (at most 200). Returns `{next_seq, control, status, remaining_applications}`. `SEQUENCE_GAP` 409 with `details.next_seq` |

## Other endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness + database check; 503 `DATABASE_UNAVAILABLE` if the DB is down |
| GET | `/plans` | Public. Active plans for the pricing page: `[{code, name, price_cents, currency, interval, limits: {applications_per_month, resumes}}]`. Falls back to `backend/app/core/plans.py` when the `plans` table is empty |

Billing and admin endpoints are added in later phases (see `docs/SAAS_ROADMAP.md`).
