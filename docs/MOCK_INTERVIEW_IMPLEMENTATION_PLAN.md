# Mock interview implementation plan — status

This document tracks the mock interview hardening and UX program. **All work packages below are implemented** in the current codebase unless noted.

## Work packages

| ID | Scope | Status |
|----|--------|--------|
| WP-01 | Async feedback jobs (`mock_interview_feedback_jobs`), Celery task, 202 + poll, inline fallback | Done |
| WP-02 | Session-scoped TTS (`POST .../messages/{id}/tts`); removed public text TTS | Done |
| WP-03 | Turn idempotency (`client_turn_id`, unique index, concurrent retry) | Done |
| WP-04 | Whisper `/transcribe` fallback when browser STT unavailable | Done |
| WP-05 | `abandoned` lifecycle (beat task), resume warnings in context, interviewer JSON retry | Done |
| WP-06 | Presenter config (`mock_interview_presenter`), static photo + live stream URL POC | Done |
| WP-07 | Barge-in, interrupt, replay last question; admin toggles | Done |
| WP-08 | Observability (structured logs, admin analytics block) | Done |

## Database

Run migrations through **0026**:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

## Operations

- **Worker:** `celery -A backend.app.worker worker --beat --pool=solo` (Redis required for async feedback; without Redis, complete/regenerate run inline).
- **Logs:** `applyxai.mock_interview`, `applyxai.mock_interview.jobs` — session create, job enqueue, job duration.
- **Admin:** Overview → mock interview counts; Settings → AI → Mock interview presenter.

## Future (vendor-dependent)

- Plug a commercial talking-avatar SDK by setting `mock_interview_presenter.mode` to `live_stream` and `live_stream_url` to the provider embed or media URL.
- Optional: dedicated admin metrics dashboard from log aggregation (Datadog/CloudWatch).

See [MOCK_INTERVIEW.md](./MOCK_INTERVIEW.md) and [API.md](./API.md#mock-interviews) for candidate and API details.
