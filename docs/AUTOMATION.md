# ApplyXAI — Automation engine integration

ApplyXAI drives the existing engine (`runAiBot.py`) without changing how it applies to jobs. The engine runs as a separate process on the user's computer. A supervisor (the desktop agent from Phase 8) gives it a config file, follows its progress through an event file, and pauses or stops it through a control file.

```
SaaS database ──► automation/run_config.py ──► config.json ──► runAiBot.py ──► events.jsonl ──► ingest_service ──► database
                                                  control ◄── pause / resume / stop
```

## Engine hooks

All hooks are off unless their environment variable is set. `python app.py` and `python runAiBot.py` never set them, so the classic workflow behaves exactly as before.

| Variable | Read by | Effect |
|---|---|---|
| `APPLYXAI_RUN_CONFIG` | `config/_overrides.py` | Read this JSON instead of `user_config.json` |
| `APPLYXAI_EVENTS_FILE` | `modules/run_hooks.py` | Append one JSON event per line |
| `APPLYXAI_CONTROL_FILE` | `modules/run_hooks.py` | Checked between jobs: `pause` idles, `stop` ends the run cleanly, anything else continues |
| `APPLYXAI_PROFILE_DIR` | `modules/open_chrome.py` | Use this Chrome profile (kept per user, so the LinkedIn sign-in survives between runs), even in `safe_mode` |

The changes to `runAiBot.py` are additive only:
- `run_hooks.emit(...)` calls where the engine already records an outcome (`submitted_jobs`, `failed_job`, the dry-run and unanswered-question skips, login, and start and end of `main()`)
- one `run_hooks.checkpoint()` per job
- a `StopRequested` handler in `main()`

`StopRequested` derives from `BaseException`, so the engine's broad `except Exception` handlers can't swallow it.

## Events

One JSON object per line, each with `event` and `ts` (ISO-8601 with offset). The full list is in `automation/events.py`:

| Event | Meaning |
|---|---|
| `run_started` | Config validated; includes `search_terms` |
| `login_required` | The user must sign in to LinkedIn in the opened browser window |
| `job_started` | The engine is looking at a job: `job_id`, `title`, `company`, `work_location`, `work_style` |
| `applied` / `external` | Easy Apply submitted, or the job uses an external site; job details included |
| `failed` / `skipped` | `job_id`, `reason`, `detail`. Title and company come from the earlier `job_started` |
| `paused` / `resumed` | Response to the control file |
| `run_finished` | Final counts, `stopped`, `daily_limit_reached`, `error` |

Screening-question answers and resume paths are never written to events.

## Run config

`automation/run_config.build_run_config(values, history_dir=, run_dir=, resume_path=, dry_run=)` takes the flat `{engine_setting: value}` mapping the SaaS stores (`backend/app/services/run_config_service.engine_values`). It sends each value to its config section using `config_schema.py`, then forces the settings a supervised run must control:

- **Output paths:** applied/failed CSVs go to the per-user `history/` folder, kept across runs so the engine never re-applies to a job it already handled. Logs and screenshots go to the run folder.
- **No stored LinkedIn credentials:** the engine gets its own placeholder pair (`username@example.com` / `example_password`), which makes it ask the user to sign in by hand. Setting any `secrets` value is refused.
- **Fixed behaviour:** AI is off, there's no run-forever mode or interactive pauses, and the browser is visible.

`missing_requirements()` reports, in plain language, what the engine's validator would reject: first and last name, a phone number of at least 10 characters, and at least one search term. A test runs the engine's own `validate_config()` against a generated config in a fresh process.

## Runner

`automation/runner.py` runs the engine for one user, with this workspace layout:

```
<workspace>/profile/            Chrome profile
<workspace>/history/            applied.csv, failed.csv (engine format)
<workspace>/runs/<run_id>/      config.json, events.jsonl, control, engine.log, logs/
```

```python
from automation.runner import EngineRun, Workspace
run = EngineRun(Workspace("C:/ApplyXAI/alice"), "8f3c...")
run.start(config)          # launches runAiBot.py in its own process group
run.new_events()           # events since the last call
run.pause(); run.resume()
run.stop(timeout=60)       # asks politely, then kills the process tree
```

## Ingestion

`backend/app/services/ingest_service.ingest_events(db, user_id, events, run=, context=, count_usage=)` handles both live events and imported history:

- **Jobs and applications:** it upserts the shared `jobs` row and the user's `applications` row. An application that's already `applied` never goes back to another status.
- **Run tracking (with `run`):** it updates the run's status, current job, and counters, writes numbered `automation_logs` lines, and sends a notification when the run finishes.
- **Batches:** pass the returned `context` along with the next batch, so `failed` and `skipped` events still get their job titles.
- **Usage:** new applications count toward the monthly plan limit unless `count_usage=False`.

## Importing existing history

To copy the classic engine's CSV history into an account (safe to repeat; imported rows don't count toward the plan limit):

```powershell
venv\Scripts\python -m backend.app.cli import-history --email you@example.com
venv\Scripts\python -m backend.app.cli import-history --email you@example.com --applied "all excels\all_applied_applications_history.csv" --failed "all excels\all_failed_applications_history.csv"
```

Without `--applied` or `--failed`, it uses the engine's configured `file_name` and `failed_file_name`.

## What's next (Phase 8)

The desktop agent will call these pieces: fetch the run settings and default resume from the API, build the config, start `EngineRun`, post `new_events()` batches back, and relay pause and stop from the Automation page. Plan limits will be enforced by writing `stop` to the control file once the month's limit is reached.
