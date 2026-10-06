"""
Builds the per-run JSON that config/_overrides.py applies over the config/*.py defaults
when APPLYXAI_RUN_CONFIG points at it.

Input is a flat {engine_setting: value} mapping (the names from config_schema.py, which is
what the SaaS stores). Each value is routed to its config section. Settings a supervised
run must control (output paths, credentials, AI, run-forever, interactive pauses) are
forced afterwards, so stored data can never change them.
"""

from pathlib import Path

import config_schema

# Placeholder credentials. The engine treats exactly this pair as "not configured" and asks
# the user to sign in by hand in the opened browser; the SaaS never handles the password.
_PLACEHOLDER_USERNAME = "username@example.com"
_PLACEHOLDER_PASSWORD = "example_password"

MIN_PHONE_LENGTH = 10


class RunConfigError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _sections() -> dict[str, str]:
    return {f["key"]: f["config_module"] for f in config_schema.iter_fields()}


def missing_requirements(values: dict) -> list[str]:
    """What the engine's validator would reject, phrased for the user."""
    problems = []
    if not str(values.get("first_name") or "").strip():
        problems.append("Add your first name to your profile.")
    if not str(values.get("last_name") or "").strip():
        problems.append("Add your last name to your profile.")
    if len(str(values.get("phone_number") or "").strip()) < MIN_PHONE_LENGTH:
        problems.append(f"Add a phone number with at least {MIN_PHONE_LENGTH} characters to your profile.")
    terms = values.get("search_terms")
    if not isinstance(terms, list) or not any(str(t).strip() for t in terms):
        problems.append("Add at least one job title or keyword to your job preferences.")
    return problems


def build_run_config(values: dict, *, history_dir: str | Path, run_dir: str | Path,
                     resume_path: str | Path | None = None, dry_run: bool = False) -> dict:
    """
    `history_dir` keeps applied/failed CSVs across runs (the engine skips jobs listed there);
    `run_dir` holds this run's logs and screenshots. Raises RunConfigError when required
    details are missing or a value names a setting the engine doesn't know.
    """
    sections = _sections()
    problems = missing_requirements(values)
    config: dict[str, dict] = {name: {} for name in ("personals", "questions", "search", "settings", "secrets")}

    for key, value in values.items():
        section = sections.get(key)
        if section is None:
            problems.append(f"Unknown setting '{key}'.")
        elif section == "secrets":
            problems.append(f"'{key}' can't be set for an ApplyXAI run.")
        elif value is not None:
            config[section][key] = value
    if problems:
        raise RunConfigError(problems)

    history, run = Path(history_dir).resolve(), Path(run_dir).resolve()
    config["settings"].update({
        "file_name": (history / "applied.csv").as_posix(),
        "failed_file_name": (history / "failed.csv").as_posix(),
        "logs_folder_path": (run / "logs").as_posix() + "/",
        "generated_resume_path": (run / "resumes").as_posix() + "/",
        "run_in_background": False,      # the user may need to sign in to LinkedIn in the window
        "run_non_stop": False,
        "alternate_sortby": False,
        "cycle_date_posted": False,
        "stop_before_submit": bool(dry_run),
        "showAiErrorAlerts": False,
    })
    config["questions"].update({
        "default_resume_path": Path(resume_path).resolve().as_posix() if resume_path else "",
        "pause_before_submit": False,
        "pause_at_failed_question": False,
    })
    config["search"]["pause_after_filters"] = False
    config["secrets"] = {
        "username": _PLACEHOLDER_USERNAME,
        "password": _PLACEHOLDER_PASSWORD,
        "use_AI": False,
        "llm_api_key": "",
    }
    return config
