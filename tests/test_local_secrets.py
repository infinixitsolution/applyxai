import json
from pathlib import Path

from agent.supervisor import _merge_local_secrets


def test_saved_logins_replace_placeholders(tmp_path: Path):
    path = tmp_path / "user_config.json"
    path.write_text(json.dumps({
        "secrets": {
            "username": "ada@example.com",
            "password": "linkedin-secret",
            "naukri_username": "ada@naukri.com",
            "naukri_password": "naukri-secret",
        }
    }), encoding="utf-8")
    config = {"secrets": {"username": "username@example.com", "password": "example_password"}}
    _merge_local_secrets(config, path)
    assert config["secrets"]["username"] == "ada@example.com"
    assert config["secrets"]["password"] == "linkedin-secret"
    assert config["secrets"]["naukri_username"] == "ada@naukri.com"
    assert config["secrets"]["naukri_password"] == "naukri-secret"


def test_blank_saved_fields_leave_placeholders(tmp_path: Path):
    path = tmp_path / "user_config.json"
    path.write_text(json.dumps({"secrets": {"username": "  ", "password": ""}}), encoding="utf-8")
    config = {"secrets": {"username": "username@example.com", "password": "example_password"}}
    _merge_local_secrets(config, path)
    assert config["secrets"]["username"] == "username@example.com"
    assert config["secrets"]["password"] == "example_password"
