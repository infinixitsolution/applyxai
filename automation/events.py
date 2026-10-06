"""
Engine events: what modules/run_hooks.py writes, one JSON object per line.

Every event has "event" and "ts" (ISO-8601, UTC). Outcome events carry the LinkedIn job id:

    run_started     search_terms
    login_required  (the user has to sign in to LinkedIn in the opened browser)
    job_started     job_id, title, company, work_location, work_style
    applied         job_id, title, company, work_location, work_style, description,
                    experience_required, reposted, date_listed, date_applied, job_link, application_link
    external        same fields as applied; the job uses an external application site
    failed          job_id, job_link, reason, detail, date_listed, application_link
    skipped         job_id, job_link, reason, detail (filtered out, or not submittable)
    paused, resumed
    limit_reached   applied (the run's application cap, APPLYXAI_MAX_APPLIED, was reached)
    run_finished    applied, external, failed, skipped, stopped, daily_limit_reached, error
"""

import json
from datetime import datetime, timezone

RUN_STARTED = "run_started"
LOGIN_REQUIRED = "login_required"
JOB_STARTED = "job_started"
APPLIED = "applied"
EXTERNAL = "external"
FAILED = "failed"
SKIPPED = "skipped"
PAUSED = "paused"
RESUMED = "resumed"
LIMIT_REACHED = "limit_reached"
RUN_FINISHED = "run_finished"

OUTCOMES = {APPLIED, EXTERNAL, FAILED, SKIPPED}
KNOWN_EVENTS = OUTCOMES | {RUN_STARTED, LOGIN_REQUIRED, JOB_STARTED, PAUSED, RESUMED, LIMIT_REACHED, RUN_FINISHED}


def validate_event(event) -> dict | None:
    """The event if it's a known kind with the fields it needs, otherwise None."""
    if not isinstance(event, dict) or event.get("event") not in KNOWN_EVENTS:
        return None
    if event["event"] in OUTCOMES | {JOB_STARTED} and not str(event.get("job_id") or "").strip():
        return None
    return event


def parse_line(line: str) -> dict | None:
    """One event, or None for a blank, malformed, or unknown line."""
    line = line.strip()
    if not line:
        return None
    try:
        return validate_event(json.loads(line))
    except ValueError:
        return None


def parse_time(value) -> datetime | None:
    """An aware UTC datetime, or None. Values without an offset are this machine's local time,
    which is how the engine writes its CSVs."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.astimezone()).astimezone(timezone.utc)


def read_events(path: str, offset: int = 0) -> tuple[list[dict], int]:
    """
    Events written since `offset` (a byte position), and the offset to pass next time.
    A final line without its newline is still being written, so it is left for the next call.
    """
    try:
        with open(path, "rb") as source:
            source.seek(offset)
            data = source.read()
    except FileNotFoundError:
        return [], offset
    end = data.rfind(b"\n")
    if end < 0:
        return [], offset
    complete = data[:end + 1]
    events = [e for e in (parse_line(raw.decode("utf-8", errors="replace")) for raw in complete.splitlines()) if e]
    return events, offset + len(complete)
