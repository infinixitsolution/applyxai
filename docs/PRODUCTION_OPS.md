# Production operations (EC2)

Runbook for P0 launch items tracked in [BACKLOG.md](./BACKLOG.md). Code ships in-repo; **you configure secrets and schedules on the host**.

## Quick verify (on the server)

```bash
cd /home/ubuntu/applyxai
bash scripts/verify_production_ops.sh
```

From Windows (uses the same SSH key as deploy):

```powershell
.\scripts\verify_ec2_ops.ps1
```

## Checklist

| Item | Action |
|------|--------|
| **PostgreSQL** | `DATABASE_URL` points at Postgres; deploy runs `alembic upgrade head` |
| **Redis** | `REDIS_URL` for Celery; **`RATE_LIMIT_STORAGE_URL=redis://127.0.0.1:6379/1`** (not `memory://`) |
| **Razorpay** | `PAYMENT_PROVIDER=razorpay` + live keys + webhook → [DEVELOPMENT.md](./DEVELOPMENT.md#payments-razorpay) |
| **Billing scope** | Razorpay is the live default; Stripe Checkout Sessions work when Admin Payments uses Stripe keys — [BILLING.md](./BILLING.md) |
| **SMTP (Hostinger)** | [EMAIL.md](./EMAIL.md); sender must be the login mailbox; test from Admin → Email |
| **Celery + beat** | `applyxai-celery.service` runs `celery … worker --beat` (single instance) |
| **Mock interview abandon** | Beat task `applyxai.abandon_stale_mock_interviews` hourly — see logs below |
| **Backups** | Install [systemd timer](./../scripts/systemd/applyxai-backup.timer) or cron example |
| **ClamAV** | Set `CLAMAV_HOST`/`CLAMAV_PORT` when `clamd` runs; leave unset to skip scanning |
| **CSP** | Enforced in [applyxai-security-headers.conf](../scripts/nginx/applyxai-security-headers.conf) (Razorpay + Stripe allowed) |
| **Security sign-off** | Complete [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) |
| **Post-deploy** | `BASE_URL=https://applyxai.com ./scripts/smoke_production.sh` |

## Celery beat and mock interview abandonment

Schedule is defined in [backend/app/worker.py](../backend/app/worker.py) (`abandon-stale-mock-interviews`, every 3600s).

Confirm on EC2:

```bash
sudo systemctl status applyxai-celery
sudo journalctl -u applyxai-celery -n 200 --no-pager | grep -E 'abandon_stale_mock_interviews|marked [0-9]+ mock interview'
```

You should see periodic `abandon_stale_mock_interviews complete abandoned=N` lines (including `N=0`).

## PostgreSQL backups

1. Install units (once):

```bash
sudo cp /home/ubuntu/applyxai/scripts/systemd/applyxai-backup.service /etc/systemd/system/
sudo cp /home/ubuntu/applyxai/scripts/systemd/applyxai-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now applyxai-backup.timer
```

2. Set env in `/etc/default/applyxai-backup` (see [applyxai-backup.service](../scripts/systemd/applyxai-backup.service)).

Optional S3: `BACKUP_S3_URI=s3://your-bucket/applyxai/` and IAM role on the instance.

## ClamAV (optional)

- **Disabled (default):** omit `CLAMAV_HOST` — uploads skip scan ([resume_malware_scan.py](../backend/app/services/resume_malware_scan.py)).
- **Enabled:** run `clamd` reachable from the API host; set `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_SCAN_TIMEOUT_SEC` in `.env`.

Document waiver in the security sign-off table if you intentionally skip ClamAV.

## Wire smoke into deploy

[update_server.sh](../scripts/update_server.sh) runs [smoke_production.sh](../scripts/smoke_production.sh) after restart and **fails the deploy** if health/public/robots/agent-release checks fail.

```bash
BASE_URL=https://applyxai.com ./scripts/smoke_production.sh
```

Ops verify (`verify_production_ops.sh`) still warns only, so a missing ClamAV host or unsigned backup timer does not roll back a code deploy.

## Leftovers close-out — host actions you must still provide

App code for these items is in-repo. They stay blocked until you configure the host (or waive them in the sign-off).

| Item | What you supply | How to verify |
|------|-----------------|---------------|
| **Razorpay live (#32)** | Live `rzp_live_…` keys + webhook `https://applyxai.com/api/billing/webhook/razorpay` (subscription events). Production rejects test keys. | Admin → Payments → Test API keys, then **Sync plans**. Buy a cheap plan on a test account. |
| **Stripe Checkout (#31)** | Optional. Stripe publishable + secret + webhook signing secret in Admin Payments (provider = Stripe). Webhook: `/api/billing/webhook/stripe`. | Checkout redirects to Stripe; GST invoice still issues on capture. |
| **Redis rate limits (#40)** | `RATE_LIMIT_STORAGE_URL=redis://127.0.0.1:6379/1` (not `memory://`) | `scripts/verify_production_ops.sh` |
| **ClamAV (#36)** | Run `clamd` + `CLAMAV_HOST` / `CLAMAV_PORT`, **or** write a waiver in [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) | Upload a resume; logs show scan or skip |
| **CSP enforce (#37)** | Deploy [applyxai-security-headers.conf](../scripts/nginx/applyxai-security-headers.conf) (enforced CSP, Razorpay + Stripe allowed) | Response header is `Content-Security-Policy`, not Report-Only. Razorpay Checkout still loads. |
| **PG backups (#34)** | Enable `applyxai-backup.timer`, set S3, **test a restore** | `systemctl list-timers applyxai-backup.timer` |
| **SPF/DKIM/DMARC (#41)** | DNS for `noreply@applyxai.com` at Hostinger | [EMAIL.md](./EMAIL.md); Admin send-test arrives outside spam |
| **Authenticode (#22)** | `CSC_LINK` / `CSC_KEY_PASSWORD` then `.\scripts\build_desktop.ps1 -Release` | Signed NSIS; SmartScreen quieter. Unsigned builds still install with a warning. |
| **RazorpayX (#33)** | `RAZORPAYX_ACCOUNT_NUMBER` (+ keys if not reusing Razorpay). Else keep **Mark paid** after a bank transfer id. | Admin → Partners → Pay now |
| **WhatsApp Cloud (#67)** | Meta WABA: `WHATSAPP_CLOUD_TOKEN`, `WHATSAPP_CLOUD_PHONE_NUMBER_ID`, verify token, app secret. Admin WhatsApp provider = Cloud. | Inbound webhook `/api/internal/outreach/whatsapp-cloud`. Bridge stays for local/dev. |
| **Security sign-off (#17/#43)** | Human fills [SECURITY_SIGNOFF_TEMPLATE.md](./SECURITY_SIGNOFF_TEMPLATE.md) | Dated owner + evidence links |

Campus **institute_managed** billing stays institute-pays (by design). Candidate `/r/` codes (`C…`) are separate from partner campus codes.
