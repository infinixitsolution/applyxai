# ApplyXAI — Automation Audit

**Date:** 2026-10-16  
**Master:** [AUDIT.md](./AUDIT.md)

## Authoritative execution path

```
User (SPA) → API AutomationService → Agent poll → automation.runner.EngineRun
  → subprocess runAiBot.py → modules/open_chrome.py → LinkedIn
  → events.jsonl → agent ingest → Application records
```

**Not authoritative for SaaS:** `app.py` Flask subprocess (classic mode only).

## Key modules

| Path | Role |
|------|------|
| `runAiBot.py` | Job loop, Easy Apply, question filling, CSV legacy |
| `modules/open_chrome.py` | Chrome/UC session, retries, Chrome update hook |
| `modules/clickers_and_finders.py` | Selenium helpers, Easy Apply modal/footer |
| `modules/chrome_update.py` | Windows Google Update before runs |
| `automation/runner.py` | Subprocess supervisor, pause/stop, workspace layout |
| `automation/run_config.py` | DB preferences → engine JSON |
| `automation/events.py` | Event line parsing |
| `automation/engine_lock.py` | One Chrome engine per machine |
| `agent/supervisor.py` | Poll loop, heartbeats, ingest |
| `agent/desktop_worker.py` | Bundled worker entry (port 39217) |

## Safety controls

| Control | Location |
|---------|----------|
| Practice / stop before submit | Engine config + `StoppedBeforeSubmit` |
| No auto legal attestations | `runAiBot.py` attestation_terms |
| Duplicate apply prevention | Applied job IDs + history CSV + DB ingest |
| External apply vs Easy Apply | `easy_apply_locators` + modal confirmation |
| CAPTCHA / challenge | No bypass — user must intervene |

## Verification

| Test | Covers |
|------|--------|
| `tests/test_selectors_groundtruth.py` | DOM fixtures vs XPath contracts |
| `tests/test_automation_runner.py` | Runner workspace / control file |
| `backend/tests/test_automation_api.py` | Run lifecycle, idle poll re-delivery |
| `backend/tests/test_ingest.py` | Event → application mapping |
| `backend/tests/test_agent_e2e.py` | Agent API integration |

## Known operational risks

1. **LinkedIn UI changes** — requires fixture updates and footer/modal helpers.
2. **Stale API process** — health marker `automation_poll: resume-idle-v2` detects old poll logic.
3. **Multiple workers** — use single desktop instance; `kill_extra_workers.ps1`.
4. **Chromedriver locks** — per-PID driver copy on Windows.

## Configuration surfaces

| Surface | Purpose |
|---------|---------|
| `/app/settings/automation` | Runtime toggles (API persisted) |
| `/app/automation/search` | Keywords, filters |
| `/app/questions` + `/api/preferences/application` | Answers merged into run config |
| Legacy `config/*.py` | Defaults when not overridden by run JSON |
