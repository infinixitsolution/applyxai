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
| **Billing scope** | Production billing is **Razorpay-only** until Stripe Checkout ships — [BILLING.md](./BILLING.md) |
| **SMTP (Hostinger)** | [EMAIL.md](./EMAIL.md); sender must be the login mailbox; test from Admin → Email |
| **Celery + beat** | `applyxai-celery.service` runs `celery … worker --beat` (single instance) |
| **Mock interview abandon** | Beat task `applyxai.abandon_stale_mock_interviews` hourly — see logs below |
| **Backups** | Install [systemd timer](./../scripts/systemd/applyxai-backup.timer) or cron example |
| **ClamAV** | Set `CLAMAV_HOST`/`CLAMAV_PORT` when `clamd` runs; leave unset to skip scanning |
| **CSP** | Report-Only in nginx snippet; move to enforce after reviewing reports |
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

## Wire smoke into deploy (optional)

Append to [update_server.sh](../scripts/update_server.sh) on the server or run manually after deploy:

```bash
BASE_URL=https://applyxai.com ./scripts/smoke_production.sh
```
