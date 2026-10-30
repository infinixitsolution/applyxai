# Outreach scrape pipeline (verified discovery)

## Overview

Admin outreach scraping uses a shared pipeline under `backend/app/services/outreach/`:

1. **Discovery** — Firecrawl search with deterministic queries (`search_queries.py`).
2. **Normalization** — URL validation, SSRF checks, hit dedupe (`search_hits.py`, `url_safety.py`).
3. **Crawl** — Prioritized page queue per candidate (`crawl_queue.py`); not gated on snippet length.
4. **Contacts** — Regex / mailto / tel extraction with provenance (`contact_extract.py`).
5. **AI** — Structured enrichment with anti-fabrication prompts; contacts gated on evidence (`evidence.py`).
6. **Identity** — Path-aware listing keys; conservative merge (`identity.py`).

Job metrics are stored in `institute_scrape_jobs.stats` (JSON) plus `leads_updated`.

## Configuration

Existing settings:

- `FIRECRAWL_API_KEY` / Admin → Integrations
- Platform AI with **Institute outreach (enrichment)**
- `OUTREACH_MAX_LEADS_PER_JOB` (default 50)

Crawl budgets are in `outreach/scrape_config.py` (conservative defaults: 5 queries, 10 results/query, 5 pages/institute, 40 pages/job).

## Celery

```powershell
celery -A backend.app.worker worker --beat --pool=solo --loglevel=info
```

If Redis accepts tasks but no worker runs, jobs stay `queued` until **stale recovery** (15 minutes, triggered on the next dispatch) runs them inline.

## Migration

```powershell
alembic -c backend/alembic.ini upgrade head
```

Adds `institute_scrape_jobs.leads_updated` and `institute_scrape_jobs.stats`.

## Job statuses

| Status | Meaning |
|--------|---------|
| `queued` | Waiting for worker |
| `running` | In progress |
| `completed` | Finished |
| `completed_with_errors` | Partial Firecrawl/AI issues; see `error_message` and `stats` |
| `failed` | Hard failure (auth, prerequisites, unrecoverable error) |

## Data quality evaluation

Labeled fixtures: `backend/tests/fixtures/outreach_eval/labeled_institutes.json` (used by manual/offline evaluation — not live API tests).

Run pipeline unit tests:

```powershell
python -m pytest backend/tests/test_outreach_scrape_pipeline.py backend/tests/test_scrape_dedupe.py -q
```

## Known limitations

- Social sources remain **search discovery** only (no logged-in scrape).
- Contact states are `syntax_valid` / `candidate` — no live deliverability checks.
- Fuzzy duplicate review uses `needs_review` status sparingly; most ambiguous pairs remain separate leads.
- Official website inference from directory pages depends on public links in crawled markdown.

## Rollback

```powershell
alembic -c backend/alembic.ini downgrade 0038
```

Deploy previous application version; new JSON fields on profiles are ignored by older code.
