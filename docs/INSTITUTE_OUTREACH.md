# Institute outreach (admin)

Admin **Outreach** discovers training institutes via Firecrawl, enriches profiles with platform AI, generates partnership proposals, and sends **email** (SMTP) plus **WhatsApp** (local QR bridge).

## Always-on automation

When **Celery worker + beat** are running, the pipeline (every ~60s, one step per tick):

1. Rotates **keyword × city** scrape jobs (configured on **Admin → Outreach → Scrape** — save campaign with compliance checked).
2. **Complete profile** for each lead; if still below **100%**, marks `skipped_incomplete` and moves on.
3. **Generate proposal** only at 100% completeness.
4. **Send email + WhatsApp** together, waiting **1–2 minutes** between leads.

From the repo root (Windows):

```powershell
celery -A backend.app.worker worker --beat --pool=solo --loglevel=info
```

Set `OUTREACH_AUTOMATION_ENABLED=false` in `.env` to disable ticks without stopping the worker.

## Firecrawl API key

Preferred: **Admin → Settings → Integrations → Institute outreach (Firecrawl)**. The key is stored encrypted in platform settings.

Optional fallback in `.env`:

```env
FIRECRAWL_API_KEY=fc-...
WHATSAPP_BRIDGE_URL=http://127.0.0.1:39219
OUTREACH_MAX_LEADS_PER_JOB=50
OUTREACH_AUTOMATION_ENABLED=true
```

Enable **Platform AI** with **Institute outreach (enrichment)** under **Admin → Settings → AI**.

## WhatsApp bridge

```powershell
cd whatsapp-bridge
npm install
npm start
```

Open **Admin → Outreach → WhatsApp**, scan the QR with WhatsApp on your phone (Linked devices). Keep the bridge process running on the same machine as the API.

Set the same shared secret in `.env` and when starting the bridge:

- API: `WHATSAPP_BRIDGE_SECRET=…`
- Bridge: `WHATSAPP_BRIDGE_SECRET=…` and `APPLYXAI_API_URL=http://127.0.0.1:8010` (or your API base URL)

When an institute replies on WhatsApp after a proposal, the bridge forwards the message to `POST /api/internal/outreach/whatsapp/inbound`. Admin sees the thread on **Outreach → Leads → lead detail** under **WhatsApp chat** and can reply from the app (outbound goes through the bridge).

**Note:** This uses WhatsApp Web automation (unofficial). For production scale, set **Admin → Outreach → WhatsApp** provider to **Cloud** and `WHATSAPP_CLOUD_TOKEN` + `WHATSAPP_CLOUD_PHONE_NUMBER_ID` (webhook `/api/internal/outreach/whatsapp-cloud`). Keep the bridge for local/dev.

## Institute portal (#68)

Campus operators use **Institute → Outreach scrape / leads / chat**. APIs live under `/api/institute/outreach/*` and are scoped by `owner_institute_id`. Admin remains the platform operator and can still see every lead.

## Compliance

- Only scrape **public** business listings; admin must check the attestation box when saving the campaign or starting a manual job.
- Email proposals include an unsubscribe line; do not send WhatsApp to numbers that are not on the public listing.

## API

Routes under `/api/admin/outreach/*` (admin session required). See OpenAPI when `APP_ENV != production`.

## Sources

| Source | Behaviour |
|--------|-----------|
| Google / web | Firecrawl search + optional page scrape |
| Facebook / Instagram / LinkedIn | Search limited to public result URLs; no logged-in scraping |
