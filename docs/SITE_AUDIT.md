# ApplyXAI site audit (operations checklist)

Last updated: 2026-10-09. Use after deploy to verify production.

## Automated on deploy (`scripts/update_server.sh`)

- Nginx site + security header snippet (robots/sitemap → API, HSTS on all responses)
- Celery worker + beat (`applyxai-celery.service`)
- Backend restart + Alembic migrations

## Manual verification

```bash
curl -sI https://applyxai.com/ | grep -i strict-transport
curl -s https://applyxai.com/sitemap.xml | head -3
curl -s https://applyxai.com/robots.txt
curl -s https://applyxai.com/api/site/public | jq '.data.branding.contact_email'
curl -s https://applyxai.com/api/plans | jq '.data.plans[].code'
```

Expected: HSTS present; sitemap is XML; robots lists `/onboarding`; contact is `support@applyxai.com`; plans exclude `unlimited`.

## Email (SES Mail Manager)

See [SES.md](./SES.md). SMTP credentials live in Admin → Email & SMTP (or EC2 `.env` fallback).

## Backups (recommended)

Schedule daily `pg_dump` from EC2 to S3 or volume snapshots — not automated in repo yet.
