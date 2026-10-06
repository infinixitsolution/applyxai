# ApplyXAI — Security

What is implemented today. Planned hardening is listed at the end.

## Classic control panel (`app.py`)

- Binds to `127.0.0.1` only, debug off.
- No CORS. Requests with a non-local `Host` header (DNS rebinding) and cross-site `POST`s (checked via `Origin` / `Sec-Fetch-Site`) are refused with 403.
- Password-type settings (LinkedIn password, AI API key) are never sent to the browser. They show as `********`, and posting that placeholder back keeps the saved value.
- Credentials still live in plain text in `user_config.json` on the user's own machine (gitignored).

## SaaS backend: authentication

| Control | Implementation |
|---|---|
| Password storage | Argon2id (`argon2-cffi` defaults), transparently re-hashed when parameters change. Plaintext passwords are never stored or logged |
| Password policy | 10–128 chars, ≥4 distinct characters, not the email address |
| Sessions | 15-minute JWT access token (HS256, audience-bound, includes a per-user `token_version`) plus a 30-day opaque refresh token |
| Cookies | Access and refresh are `HttpOnly; SameSite=Lax`, `Secure` in production; refresh is scoped to `/api/auth` |
| Refresh rotation | Every refresh issues a new token and retires the old one. Replaying a retired token (outside a 10 s two-tab grace window) revokes **all** of the user's sessions |
| Revocation | Bumping `users.token_version` invalidates every outstanding access token immediately (logout-all, password reset, refresh-token theft) |
| CSRF | Double-submit token: state-changing requests that carry an auth cookie must send `X-CSRF-Token` matching the `applyxai_csrf` cookie (constant-time compare) |
| Email tokens | 256-bit random, stored only as SHA-256, single use, expiring (verify 24h, reset 60 min); issuing a new one voids older ones |
| Account enumeration | Register, resend-verification, and forgot-password give identical responses for known and unknown emails. Login gives the same error for a wrong password and an unknown email, and burns an equal Argon2 verification for unknown emails to defeat timing |
| Rate limiting | Moving-window limits per IP and per email on login, register, verification, and reset endpoints (`limits` library; Redis required in production). `429` with `Retry-After` |
| Verification | Login requires a verified email (`REQUIRE_EMAIL_VERIFICATION`, on by default) |

## SaaS backend: general

- Errors use the standard envelope. Unhandled exceptions return `INTERNAL_ERROR` and are logged server-side; tracebacks never reach the client.
- CORS: explicit allow-list (`CORS_ORIGINS`) with credentials. Unknown origins get no CORS headers.
- SQL only through the SQLAlchemy ORM / expression language (bound parameters).
- Configuration is environment-only (`.env` is gitignored). With `APP_ENV=production` the API **refuses to start** unless all of these hold:
  - `SECRET_KEY` and `JWT_SECRET` are set (≥32 chars)
  - `DATABASE_URL` is PostgreSQL
  - SMTP is configured
  - `PAYMENT_PROVIDER` is real (not `null`)
  - cookies are Secure
  - rate-limit storage is shared (Redis)
- In development without SMTP, emails (including their one-time links) are printed to the API console. This is intentional for local testing and impossible in production because of the check above.
- Behind a reverse proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>` so rate limits see real client IPs.

## SaaS backend: user data

- Every profile, preference, and resume query is filtered by the logged-in user's ID. Another user's resource answers `404`, not `403`, so IDs can't be probed. `backend/tests/test_isolation.py` checks this with two real sessions.
- Jobs are a shared catalogue, but every jobs query starts from the caller's own applications. A user can see a job only if their automation encountered it, and only with their own application status.
- Applications, usage counters, and notifications are written server-side only (by the automation worker). The browser has read-only access, apart from marking notifications as read.
- The CSV export escapes cells beginning with `= + - @` (CSV/formula injection), since job titles and companies come from third-party pages.
- Search input is matched literally: `%` and `_` are escaped before `ILIKE`. Sort columns come from a fixed whitelist.
- Preferences only accept whitelisted engine settings, validated against the engine's own rules. The API never accepts LinkedIn credentials or AI API keys (those stay on the user's machine, with the desktop agent).
- Resume uploads:
  - PDF and DOCX only. The content must match: `%PDF-` header, or a real DOCX zip with `word/document.xml`. Macro-enabled documents are rejected, and so is a declared MIME type that contradicts the extension.
  - Read in chunks and capped at `MAX_RESUME_BYTES` (5 MB).
  - Stored as `STORAGE_DIR/resumes/<user_id>/<random>.pdf|docx`. The uploaded filename is sanitised and kept for display only; it never becomes part of a path.
  - Downloads are always attachments with `X-Content-Type-Options: nosniff` and `Cache-Control: private, no-store`.
  - The resume count is checked server-side against the plan (`backend/app/core/plans.py`, later the `plans` table).

## Desktop agent

- Pairing codes are 8 characters from a 32-symbol alphabet (40 bits), valid 10 minutes, single use, and stored only as SHA-256. Asking for a new code voids the previous one. Pairing is rate-limited per IP, and code generation per user.
- Device tokens (`axd_` + 256 random bits) are shown to the agent once and stored only as SHA-256. The agent keeps its copy in its own folder (owner-only permissions on macOS and Linux) and never prints it.
- Agent endpoints accept only `Authorization: Bearer`, never cookies, so a web page can't drive them. CORS doesn't allow the `Authorization` header.
- Removing a computer, logging out everywhere, resetting the password, and refresh-token reuse all revoke device tokens. The agent stops its engine on the next 401.
- A device acts only for its own user: it can claim only that user's queued runs, and report events, download the resume, or read control only for runs it claimed. Anything else is `404`. `backend/tests/test_automation_api.py` checks this with two users.
- The server never receives LinkedIn credentials. The engine gets placeholder credentials, so the user signs in by hand in the browser window on their own computer. The server rechecks readiness and the plan limit when a run is claimed, so a stale browser tab can't get around them.
- The agent refuses plain `http://` servers other than `localhost` unless `--insecure` is given.

## Billing

- A plan is granted only from data the server fetched from Razorpay itself. The checkout callback's signature (HMAC-SHA256 of `payment_id|subscription_id` with the key secret) is checked first, then the subscription and payment are re-read from Razorpay's API. The browser can't send a price, plan status, or "paid" flag that is believed.
- Webhooks are refused unless `X-Razorpay-Signature` matches the HMAC-SHA256 of the raw body with `PAYMENT_WEBHOOK_SECRET` (constant-time compare). Each event ID is applied once, and the subscription's state is re-read from Razorpay rather than taken from the payload, so replayed or reordered events can't change it.
- A user can only confirm, cancel, or see their own subscriptions and payments (`backend/tests/test_billing_api.py` checks this with two users).
- Card and UPI details never reach ApplyXAI; Checkout runs on Razorpay. Webhook payloads (which contain contact details) aren't stored, and Razorpay's error descriptions are logged server-side, not shown to users.
- `PAYMENT_PROVIDER=null` (plans for free) is refused in production, and production also requires `PAYMENT_KEY_ID`, `PAYMENT_SECRET`, and `PAYMENT_WEBHOOK_SECRET`.

## Admin

- Every `/api/admin/*` route depends on `require_admin`, which reloads the user from the database on each request, so removing `is_admin` takes effect immediately. Non-admins get 403; the web app's `/admin` guard is only for convenience. `backend/tests/test_admin_api.py` checks every admin route with a regular user.
- Admins can't disable themselves or remove their own admin access, so the last admin can't lock everyone out by accident. Grant admin access from the command line with `python -m backend.app.cli make-admin --email ...`.
- Admin views show account, plan, usage, and run data, but never password hashes, resume files, form answers, tokens, or payment details.
- Every change an admin makes (account flags, complimentary plans, plan edits, stopping a run) is recorded in `admin_actions` with the admin's email, the target, and the before/after values. The rows outlive deleted accounts (foreign keys are `SET NULL`).
- Disabling an account revokes its sessions and desktop agents at once and stops a run in progress.
- Complimentary plans never touch the payment provider, and they're refused while the user has a paid plan, so an admin can't silently change what someone is billed for.

## Never commit

`.env`, `user_config.json`, `storage/`, LinkedIn credentials, API keys, payment secrets, cookies, or session tokens. These paths are in `.gitignore`.

## Planned (later phases)

- Malware scanning of uploads (for example ClamAV) before production launch (Phase 12)
- Security headers (HSTS, CSP, frame-ancestors), structured JSON logs with secret redaction, dependency pinning, and backups (Phase 12)
