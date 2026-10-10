# Security sign-off template (#17 / #43)

Use before production launch. Attach evidence links (screenshots, config exports, scan reports).

| Control | Owner | Date | Evidence |
|---------|-------|------|----------|
| [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) agent + API items complete | | | |
| Production secrets (SECRET_KEY, JWT_SECRET, Fernet) rotated | | | |
| PAYMENT_PROVIDER + webhook secrets configured | | | |
| RATE_LIMIT_STORAGE_URL = Redis (not memory) | | | |
| TLS + HSTS on public nginx | | | |
| CSP report-only reviewed; enforce plan dated | | | |
| ClamAV (`CLAMAV_HOST`) or documented waiver | | | |
| PostgreSQL backups scheduled (`scripts/backup_postgres.sh`) | | | |
| Celery worker **with beat** for mock interview abandon job | | | |

**Sign-off:** _________________________  **Role:** _____________  **Date:** _____________
