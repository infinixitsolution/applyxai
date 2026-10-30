"""Profile sync agent path with stand-in engine."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import automation.runner as runner_module
from agent.client import ApiClient
from agent.supervisor import Supervisor
from backend.app.models import User
from backend.tests.conftest import csrf_headers
from backend.tests.test_automation_api import pair

PROFILE_STANDIN = '''
import os, sys
sys.path.insert(0, os.getcwd())
from modules import run_hooks
run_hooks.emit("profile_sync_started", sections=["headline"])
run_hooks.emit("profile_section_updated", section="headline", field="headline", detail="standin")
run_hooks.emit("profile_sync_finished", updated=1, skipped=0, failed=0, stopped=False, error="")
'''


@pytest.fixture
def profile_engine_script(tmp_path, monkeypatch):
    script = tmp_path / "profile_engine.py"
    script.write_text(PROFILE_STANDIN, encoding="utf-8")
    monkeypatch.setattr(runner_module, "PROFILE_SYNC_SCRIPT", script)
    return script


class AgentHttp:
    def __init__(self, app):
        self._client = TestClient(app)

    def request(self, method, url, timeout=None, **kwargs):
        kwargs.pop("verify", None)
        kwargs.pop("timeout", None)
        return self._client.request(method, url, **kwargs)


@pytest.fixture
def profile_ready(make_user):
    alice = make_user("profilesync@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "phone": "9876543210",
            "headline": "Engineer",
            "skills": ["Python", "SQL", "Go"],
            "work_history": [{"title": "Dev", "company": "Acme", "start": "2020"}],
        },
        headers=h,
    )
    alice.patch(
        "/api/profile/sections/career",
        json={"data": {"linkedin_url": "https://www.linkedin.com/in/me/"}},
        headers=h,
    )
    return alice


def test_profile_sync_dry_run_e2e(app, db, profile_ready, profile_engine_script, tmp_path):
    alice = profile_ready
    agent_http = AgentHttp(app)
    agent = pair(app, alice)
    token = agent.headers["Authorization"].split(" ", 1)[1]
    agent_client = ApiClient("http://testserver", token=token, session=agent_http)

    run_id = alice.post(
        "/api/automation/profile-sync/start",
        json={"dry_run": True},
        headers=csrf_headers(alice),
    ).json()["data"]["id"]

    user = db.query(User).filter_by(email="profilesync@example.com").one()
    home = tmp_path / "agent_home"
    sup = Supervisor(agent_client, home, str(user.id))
    poll = agent_client.poll()
    assert poll["run"]["id"] == run_id
    assert poll["run"]["run_kind"] == "linkedin_profile_sync"
    sup.execute(poll["run"])

    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["status"] in ("completed", "failed")
