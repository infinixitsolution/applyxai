'''
Optional hooks that let an outside supervisor (the ApplyXAI desktop agent) follow and
steer a run. Every hook is a no-op unless its environment variable is set, so the
classic `python app.py` / `python runAiBot.py` workflow behaves exactly as before.

    APPLYXAI_EVENTS_FILE   append one JSON object per line for each outcome
    APPLYXAI_CONTROL_FILE  read between jobs: "pause" idles, "stop" ends the run cleanly
    APPLYXAI_PROFILE_DIR   dedicated Chrome profile for this user (see open_chrome.py)
    APPLYXAI_MAX_APPLIED   stop at the next checkpoint once this many "applied" events were
                           emitted (the plan's remaining monthly applications)

The event format is documented in automation/events.py, which also reads these files.

License: MIT  (https://opensource.org/license/mit)
'''

import json
import os
import time
from datetime import datetime, timezone

EVENTS_ENV = "APPLYXAI_EVENTS_FILE"
CONTROL_ENV = "APPLYXAI_CONTROL_FILE"
PROFILE_ENV = "APPLYXAI_PROFILE_DIR"
MAX_APPLIED_ENV = "APPLYXAI_MAX_APPLIED"

MAX_TEXT = 20_000
PAUSE_POLL_SECONDS = 2.0

_applied = 0


class StopRequested(BaseException):
    '''
    Raised at a checkpoint when the supervisor asks the run to stop. It derives from
    BaseException on purpose: the engine wraps whole search loops in `except Exception`,
    and a stop request must not be swallowed there and treated as a page error.
    '''


def _clean(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        # The engine uses naive local times (datetime.now()); attach this machine's offset.
        return (value if value.tzinfo else value.astimezone()).isoformat()
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    text = str(value)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "...[TRUNCATED]"


def emit(event: str, **fields) -> None:
    '''Append an event to APPLYXAI_EVENTS_FILE. Never raises: a broken sink must not stop a run.'''
    global _applied
    if event == "applied":
        _applied += 1
    path = os.environ.get(EVENTS_ENV)
    if not path:
        return
    record = {"event": event, "ts": datetime.now(timezone.utc).isoformat()}
    record.update({key: _clean(value) for key, value in fields.items()})
    try:
        with open(path, "a", encoding="utf-8") as sink:
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_control() -> str:
    path = os.environ.get(CONTROL_ENV)
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as control:
            return control.read().strip().lower()
    except OSError:
        return ""


def _application_limit_reached() -> bool:
    try:
        return _applied >= int(os.environ.get(MAX_APPLIED_ENV, ""))
    except ValueError:
        return False


def _apply_profile_refresh() -> None:
    """Hot-reload Master Profile / custom QA written by the supervisor for the next job."""
    run_config = os.environ.get("APPLYXAI_RUN_CONFIG")
    if not run_config:
        return
    refresh_path = os.path.join(os.path.dirname(run_config), "profile_refresh.json")
    if not os.path.isfile(refresh_path):
        return
    try:
        with open(refresh_path, encoding="utf-8") as fh:
            blob = json.load(fh)
        os.remove(refresh_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return
    if not isinstance(blob, dict):
        return
    try:
        with open(run_config, encoding="utf-8") as fh:
            config = json.load(fh)
        if not isinstance(config, dict):
            return
        qa = blob.get("application_qa") if isinstance(blob.get("application_qa"), dict) else {}
        values = blob.get("values") if isinstance(blob.get("values"), dict) else {}
        applyxai = config.setdefault("applyxai", {})
        if "human_questions" in qa:
            applyxai["human_questions"] = qa.get("human_questions") or []
        if "ai_policy" in qa:
            applyxai["ai_policy"] = qa.get("ai_policy") or applyxai.get("ai_policy")
        if "education" in qa:
            applyxai["education"] = qa.get("education") or []
        questions = config.setdefault("questions", {})
        personals = config.setdefault("personals", {})
        for key, value in values.items():
            if key in personals or key in ("first_name", "last_name", "phone_number", "linkedIn", "website"):
                personals[key] = value
            elif key in ("user_information_all",):
                questions[key] = value
            elif key in questions:
                questions[key] = value
        with open(run_config, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
        import importlib
        import config.applyxai as ax
        import config.personals as personals_mod
        import config.questions as questions_mod
        import config._overrides as overrides
        importlib.reload(overrides)
        overrides.apply(ax.__name__, ax.__dict__)
        overrides.apply(personals_mod.__name__, personals_mod.__dict__)
        overrides.apply(questions_mod.__name__, questions_mod.__dict__)
    except Exception:
        pass


def checkpoint(sleep=time.sleep) -> None:
    '''
    Called between jobs. Returns immediately when no supervisor is attached. While the
    control file says "pause", idles; "stop", or reaching APPLYXAI_MAX_APPLIED, raises
    StopRequested.
    '''
    if not os.environ.get(CONTROL_ENV):
        return
    _apply_profile_refresh()
    if _application_limit_reached():
        emit("limit_reached", applied=_applied)
        raise StopRequested()
    state = read_control()
    if state == "pause":
        emit("paused")
        while state == "pause":
            sleep(PAUSE_POLL_SECONDS)
            state = read_control()
        if state != "stop":
            emit("resumed")
    if state == "stop":
        raise StopRequested()


def profile_dir() -> str | None:
    '''The dedicated Chrome profile directory for this run, created if needed.'''
    path = os.environ.get(PROFILE_ENV)
    if not path:
        return None
    os.makedirs(path, exist_ok=True)
    return path
