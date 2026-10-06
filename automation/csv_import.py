"""
Reads the engine's history CSVs (settings.file_name / failed_file_name) and turns each row
into the same event shape modules/run_hooks.py writes, so one ingestion path handles both.

Rows without a job id are ignored. Columns are looked up by header name, so older CSVs
with missing columns still import.
"""

import csv
import sys

from automation import events as ev

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def _value(row: dict, column: str) -> str:
    return (row.get(column) or "").strip()


def _known(value: str) -> str:
    return "" if value in ("Unknown", "Pending", "Not Available", "None") else value


def read_applied(path: str) -> list[dict]:
    events = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as source:
        for row in csv.DictReader(source):
            job_id = _value(row, "Job ID")
            if not job_id or not _value(row, "Title"):
                continue
            link = _value(row, "External Job link")
            events.append({
                "event": ev.APPLIED if link in ("", "Easy Applied") else ev.EXTERNAL,
                "ts": _known(_value(row, "Date Applied")),
                "job_id": job_id,
                "title": _value(row, "Title"),
                "company": _value(row, "Company"),
                "work_location": _value(row, "Work Location"),
                "work_style": _value(row, "Work Style"),
                "description": _known(_value(row, "About Job")),
                "date_listed": _known(_value(row, "Date Posted")),
                "date_applied": _known(_value(row, "Date Applied")),
                "job_link": _value(row, "Job Link"),
                "application_link": link,
            })
    return events


def read_failed(path: str) -> list[dict]:
    events = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as source:
        for row in csv.DictReader(source):
            job_id = _value(row, "Job ID")
            if not job_id:
                continue
            link = _value(row, "External Job link")
            events.append({
                "event": ev.SKIPPED if link == "Skipped" else ev.FAILED,
                "ts": _known(_value(row, "Date Tried")),
                "job_id": job_id,
                "job_link": _value(row, "Job Link"),
                "date_listed": _known(_value(row, "Date listed")),
                "reason": _value(row, "Assumed Reason"),
                "application_link": link,
            })
    return events


def read_history(applied_path: str | None = None, failed_path: str | None = None) -> list[dict]:
    """Failed attempts first, then successes, so a job that failed once and later succeeded ends as applied."""
    events = []
    if failed_path:
        events += read_failed(failed_path)
    if applied_path:
        events += read_applied(applied_path)
    return events
