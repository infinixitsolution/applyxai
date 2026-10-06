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
| `APPLYXAI_MAX_APPLIED` | `modules/run_hooks.py` | Once this many `applied` events were emitted, the next checkpoint emits `limit_reached` and ends the run cleanly (the plan's remaining monthly applications). Needs `APPLYXAI_CONTROL_FILE` |

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
| `limit_reached` | `APPLYXAI_MAX_APPLIED` was reached; `applied` |
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
run.start(config, max_applied=6)   # launches runAiBot.py in its own process group
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

## Desktop agent

Runs never execute on the server. The user starts one on the Automation page, and the ApplyXAI agent (`agent/`) on their own computer picks it up and runs the engine there, in a browser they can see and sign in to themselves.

```
Automation page ──POST /api/automation/start──► automation_jobs (queued)
agent ──POST /api/agent/poll──► claims the run ──► downloads the default resume ──► build_run_config ──► EngineRun
agent ──POST /api/agent/runs/{id}/events (numbered batches)──► ingest_service ──► reply: {next_seq, control, remaining_applications}
Pause / Resume / Stop ──► automation_jobs.control ──► next reply ──► control file
```

### Using it

```powershell
# On the Automation page: "Connect a computer" shows a one-time code (valid 10 minutes)
venv\Scripts\python -m agent pair --server https://app.example.com --code ABCD-2345
venv\Scripts\python -m agent run          # waits for runs; Ctrl+C stops the current run cleanly
venv\Scripts\python -m agent status --check
venv\Scripts\python -m agent unpair
```

- The agent keeps its token and workspace in `%LOCALAPPDATA%\ApplyXAI\agent` (or `APPLYXAI_AGENT_HOME`, or `--home`). The workspace holds the per-user Chrome profile, the engine's history CSVs, and one folder per run.
- Plain `http://` servers are refused except `localhost`, unless `--insecure` is given.
- An account can pair up to 5 computers. Removing a computer on the website, logging out everywhere, or resetting the password disconnects it, and a running engine is stopped.

### Reliability

- **Claiming:** a run is claimed with one atomic update, so two computers can't both take it. At claim time the server checks readiness (profile, search terms, a default resume) and the plan limit again, and fails the run with a clear message if either fails.
- **Events:** every engine event gets a sequence number and stays in the agent's outbox until the server confirms it. A resent batch skips numbers already stored, and a gap is refused with `409 SEQUENCE_GAP` and the number to resend from. Nothing is lost or counted twice when the connection drops.
- **Heartbeat:** the agent posts at least every 5 seconds while a run is active. Its reply carries the latest pause, resume, or stop.
- **Silent computers:** a run whose agent hasn't been heard from for 3 minutes is marked failed, and a queued run nobody picks up within 24 hours is cancelled. A Celery beat task (`applyxai.reap_stale_runs`) checks every minute, and the Automation page also checks when it loads. If the agent restarts while it held a run, its next poll marks that run failed.
- **Crashes:** if the engine exits without a final event, the agent reports the counts so far and the exit code.

### Plan limits

The remaining monthly applications are checked when a run starts and again when it's claimed. During the run, three layers keep it within the limit:

1. The engine gets `APPLYXAI_MAX_APPLIED` and stops by itself at the next checkpoint once it has applied that many times.
2. The agent counts applications the server hasn't confirmed yet and writes `stop` when they reach the limit.
3. The server sets the run's control to `stop` once usage reaches the limit.

The run ends as `cancelled` with `stop_reason = plan_limit`, and the user gets a notification linking to Billing. Practice runs (`dry_run`) submit nothing and have no cap.
