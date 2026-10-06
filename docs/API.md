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

## Other endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness + database check; 503 `DATABASE_UNAVAILABLE` if the DB is down |

Profile, resumes, preferences, jobs, applications, automation, billing, and admin endpoints are added in later phases (see `docs/SAAS_ROADMAP.md`).
