"""
Engine events: what modules/run_hooks.py writes, one JSON object per line.

Every event has "event" and "ts" (ISO-8601, UTC). Outcome events carry the LinkedIn job id:

    run_started     search_terms
    login_required  platform (the user has to sign in to that site in the opened browser)
    source_started  source
    source_switched source, submitted_on_previous
    source_blocked  source, reason
    job_started     job_id, title, company, work_location, work_style, platform, job_link
    applied         job_id, title, company, work_location, work_style, description,
                    experience_required, reposted, date_listed, date_applied, job_link, application_link
    external        same fields as applied; the job uses an external application site
    failed          job_id, job_link, reason, detail, date_listed, application_link
    skipped         job_id, job_link, reason, detail (filtered out, or not submittable)
    paused, resumed
    limit_reached   applied (the run's application cap, APPLYXAI_MAX_APPLIED, was reached)
    run_finished    applied, external, failed, skipped, stopped, daily_limit_reached, error
    form_question   label, question_type, options, needs_answer, job_id (optional)
"""

import json
from datetime import datetime, timezone

RUN_STARTED = "run_started"
LOGIN_REQUIRED = "login_required"
SOURCE_STARTED = "source_started"
SOURCE_SWITCHED = "source_switched"
SOURCE_BLOCKED = "source_blocked"
JOB_STARTED = "job_started"
APPLIED = "applied"
EXTERNAL = "external"
FAILED = "failed"
SKIPPED = "skipped"
PAUSED = "paused"
RESUMED = "resumed"
LIMIT_REACHED = "limit_reached"
RUN_FINISHED = "run_finished"
FORM_QUESTION = "form_question"

PROFILE_SYNC_STARTED = "profile_sync_started"
PROFILE_SECTION_STARTED = "profile_section_started"
PROFILE_SECTION_UPDATED = "profile_section_updated"
PROFILE_SECTION_SKIPPED = "profile_section_skipped"
PROFILE_MANUAL_REQUIRED = "profile_manual_required"
PROFILE_SYNC_FINISHED = "profile_sync_finished"

OUTCOMES = {APPLIED, EXTERNAL, FAILED, SKIPPED}
SOURCE_EVENTS = {SOURCE_STARTED, SOURCE_SWITCHED, SOURCE_BLOCKED}
PROFILE_EVENTS = {
    PROFILE_SYNC_STARTED,
    PROFILE_SECTION_STARTED,
    PROFILE_SECTION_UPDATED,
    PROFILE_SECTION_SKIPPED,
    PROFILE_MANUAL_REQUIRED,
    PROFILE_SYNC_FINISHED,
}
KNOWN_EVENTS = OUTCOMES | SOURCE_EVENTS | PROFILE_EVENTS | {
    RUN_STARTED, LOGIN_REQUIRED, JOB_STARTED, PAUSED, RESUMED, LIMIT_REACHED, RUN_FINISHED, FORM_QUESTION,
}


def validate_event(event) -> dict | None:
    """The event if it's a known kind with the fields it needs, otherwise None."""
    if not isinstance(event, dict) or event.get("event") not in KNOWN_EVENTS:
        return None
    if event["event"] == FORM_QUESTION:
        return event if str(event.get("label") or "").strip() else None
    if event["event"] in SOURCE_EVENTS and event.get("source") not in ("linkedin", "naukri"):
        return None
    if event["event"] in PROFILE_EVENTS:
        if event["event"] in {PROFILE_SECTION_STARTED, PROFILE_SECTION_UPDATED, PROFILE_SECTION_SKIPPED}:
            return event if str(event.get("section") or "").strip() else None
        return event
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
