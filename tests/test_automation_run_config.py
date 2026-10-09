'''
automation/run_config.py: routing values to config sections, the settings a supervised run
always forces, and an end-to-end check that the engine's own validator accepts the result
when loaded through APPLYXAI_RUN_CONFIG.

License: MIT  (https://opensource.org/license/mit)
'''

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from automation.run_config import RunConfigError, build_run_config, missing_requirements

ROOT = Path(__file__).resolve().parent.parent

VALUES = {
    "first_name": "Priya", "last_name": "Sharma", "phone_number": "+91 98765 43210",
    "years_of_experience": "4", "current_city": "Bengaluru",
    "search_terms": ["Python Developer"], "search_location": "Bengaluru, India",
    "experience_level": ["Entry level"], "job_type": ["Full-time"], "on_site": ["Remote"],
    "date_posted": "Past week", "easy_apply_only": True, "bad_words": ["unpaid"],
    "desired_salary": 1_200_000, "require_visa": "No", "follow_companies": False,
}


def build(tmp_path, values=VALUES, **kwargs):
    return build_run_config(values, history_dir=tmp_path / "history", run_dir=tmp_path / "runs" / "r1", **kwargs)


def test_resume_mode_from_values_goes_to_applyxai_section(tmp_path):
    config = build(tmp_path, {**VALUES, "resume_mode": "tailor_if_gate"})
    assert config["applyxai"]["resume_mode"] == "tailor_if_gate"
    assert "resume_mode" not in config["search"]


def test_values_are_routed_to_their_engine_sections(tmp_path):
    config = build(tmp_path)
    assert config["personals"]["first_name"] == "Priya" and config["personals"]["current_city"] == "Bengaluru"
    assert config["questions"]["years_of_experience"] == "4" and config["questions"]["desired_salary"] == 1_200_000
    assert config["search"]["experience_level"] == ["Entry level"] and config["search"]["bad_words"] == ["unpaid"]
    assert config["settings"]["follow_companies"] is False


def test_supervised_run_settings_are_forced(tmp_path):
    sneaky = {**VALUES, "run_in_background": True, "pause_before_submit": True, "overwrite_previous_answers": True}
    config = build(tmp_path, sneaky, resume_path=tmp_path / "cv.pdf")
    settings, secrets = config["settings"], config["secrets"]
    assert settings["file_name"].endswith("history/applied.csv")
    assert settings["failed_file_name"].endswith("history/failed.csv")
    assert settings["logs_folder_path"].endswith("runs/r1/logs/")
    assert settings["run_in_background"] is False and settings["run_non_stop"] is False
    assert settings["stop_before_submit"] is False
    assert config["questions"]["pause_before_submit"] is False
    assert config["questions"]["overwrite_previous_answers"] is True        # a normal answer, kept
    assert config["questions"]["default_resume_path"].endswith("cv.pdf")
    # The engine's "not configured" credentials: the user signs in by hand, nothing is stored.
    assert secrets == {"username": "username@example.com", "password": "example_password",
                       "use_AI": False, "llm_api_key": ""}
    assert build(tmp_path, dry_run=True)["settings"]["stop_before_submit"] is True


def test_secrets_and_unknown_settings_are_refused(tmp_path):
    with pytest.raises(RunConfigError) as err:
        build(tmp_path, {**VALUES, "password": "hunter22", "llm_api_key": "sk-x", "made_up": 1})
    assert len(err.value.problems) == 3


def test_missing_requirements_are_explained(tmp_path):
    assert missing_requirements(VALUES) == []
    problems = missing_requirements({"first_name": " ", "phone_number": "123", "search_terms": [" "]})
    assert len(problems) == 4
    with pytest.raises(RunConfigError):
        build(tmp_path, {**VALUES, "search_terms": []})


def test_the_engine_validator_accepts_the_generated_config(tmp_path):
    config = build(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    script = (
        "import json\n"
        "from modules.validator import validate_config\n"
        "import config.settings as s, config.search as q, config.secrets as c\n"
        "validate_config()\n"
        "print(json.dumps([s.file_name, q.search_terms, q.experience_level, c.username]))\n"
    )
    env = {**os.environ, "APPLYXAI_RUN_CONFIG": str(path)}
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    file_name, terms, levels, username = json.loads(done.stdout.strip().splitlines()[-1])
    assert file_name == config["settings"]["file_name"]
    assert terms == ["Python Developer"] and levels == ["Entry level"]
    assert username == "username@example.com"
