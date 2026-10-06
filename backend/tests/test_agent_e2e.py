"""
The whole path with nothing faked but the browser: the real API, the real agent client and
supervisor, and a real engine subprocess (a stand-in for runAiBot.py that uses the same
hooks) talking through the real config, event, and control files.
"""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import automation.runner as runner_module
from agent.client import ApiClient
from agent.supervisor import Supervisor
from backend.app.models import Application, ApplicationStatus, UsageCounter, User
from backend.app.services.usage_service import current_period
from backend.tests.conftest import csrf_headers
from backend.tests.test_automation_api import make_ready
from backend.tests.test_resumes_api import PDF

STAND_IN_ENGINE = '''
import json, os, sys, time
sys.path.insert(0, os.getcwd())
from modules import run_hooks
config = json.load(open(os.environ["APPLYXAI_RUN_CONFIG"], encoding="utf-8"))
resume = config["questions"]["default_resume_path"]
json.dump({"resume": open(resume, "rb").read().decode("latin-1"), "username": config["secrets"]["username"],
           "stop_before_submit": config["settings"]["stop_before_submit"]},
          open(os.path.join(os.path.dirname(os.environ["APPLYXAI_RUN_CONFIG"]), "seen.json"), "w"))
if os.environ.get("STAND_IN_CRASH"):
    run_hooks.emit("run_started", search_terms=config["search"]["search_terms"])
    sys.exit(3)
run_hooks.emit("run_started", search_terms=config["search"]["search_terms"])
counts = {"applied": 0, "failed": 0, "skipped": 0}
stopped = False
try:
    for n in range(1, 200):
        run_hooks.checkpoint(sleep=lambda s: time.sleep(0.05))
        run_hooks.emit("job_started", job_id=str(n), title="Job %d" % n, company="Acme", work_location="Pune", work_style="Remote")
        if n <= int(os.environ.get("STAND_IN_APPLY", "1")):
            run_hooks.emit("applied", job_id=str(n), title="Job %d" % n, company="Acme",
                           job_link="https://www.linkedin.com/jobs/view/%d" % n)
            counts["applied"] += 1
        elif n == int(os.environ.get("STAND_IN_APPLY", "1")) + 1:
            run_hooks.emit("failed", job_id=str(n), reason="Form error", detail="Missing field")
            counts["failed"] += 1
        else:
            run_hooks.emit("skipped", job_id=str(n), reason="Filtered")
            counts["skipped"] += 1
        time.sleep(0.05)
except run_hooks.StopRequested:
    stopped = True
run_hooks.emit("run_finished", external=0, stopped=stopped, error="", daily_limit_reached=False, **counts)
'''


@pytest.fixture
def engine_script(tmp_path, monkeypatch):
    script = tmp_path / "engine.py"
    script.write_text(STAND_IN_ENGINE, encoding="utf-8")
    monkeypatch.setattr(runner_module, "ENGINE_SCRIPT", script)
    return script


class AgentHttp:
    """The agent's HTTP session, served by the app in-process (TestClient ignores timeouts)."""

    def __init__(self, app):
        self._client = TestClient(app)

    def request(self, method, url, timeout=None, **kwargs):
        return self._client.request(method, url, **kwargs)


@pytest.fixture
def setup(app, make_user, tmp_path, engine_script):
    alice = make_ready(make_user("alice@example.com", client=TestClient(app)))
    code = alice.post("/api/automation/devices/pairing-code", headers=csrf_headers(alice)).json()["data"]["code"]
    agent_http = AgentHttp(app)
    paired = ApiClient("http://testserver", session=agent_http).pair(code, "Test PC")
    client = ApiClient("http://testserver", paired["token"], session=agent_http)
    return alice, client, paired["user_id"], tmp_path / "agent-home"


def supervisor(client, home, user_id, on_tick=lambda: None):
    def sleep(_seconds):
        on_tick()
        time.sleep(0.05)
    return Supervisor(client, home, user_id, sleep=sleep)


def run_view(alice, run_id):
    return alice.get(f"/api/automation/{run_id}").json()["data"]


def seen(home, user_id, run_id):
    return json.loads((Path(home) / "workspace" / user_id / "runs" / run_id / "seen.json").read_text())


def test_a_run_started_on_the_website_runs_on_the_computer_and_stops_on_request(db, setup):
    alice, client, user_id, home = setup
    run_id = alice.post("/api/automation/start", json={}, headers=csrf_headers(alice)).json()["data"]["id"]
    asked = []

    def stop_after_a_few_jobs():
        if not asked and run_view(alice, run_id)["total_jobs"] >= 3:
            asked.append(alice.post(f"/api/automation/{run_id}/stop", headers=csrf_headers(alice)).status_code)

    assert supervisor(client, home, user_id, stop_after_a_few_jobs).run_once() is True
    assert asked == [200]

    run = run_view(alice, run_id)
    assert run["status"] == "cancelled" and run["stop_reason"] == "user"
    assert run["successful_count"] == 1 and run["failed_count"] == 1 and run["skipped_count"] >= 1
    statuses = {a.status for a in db.query(Application).all()}
    assert statuses >= {ApplicationStatus.APPLIED, ApplicationStatus.FAILED, ApplicationStatus.SKIPPED}
    logs = [i["event"] for i in alice.get(f"/api/automation/{run_id}/logs").json()["data"]["items"]]
    assert logs[0] == "claimed" and logs[1] == "run_started" and logs[-1] == "run_finished"
    assert alice.get(f"/api/automation/{run_id}/logs").json()["data"]["items"][-1]["message"] == "Run stopped at your request."

    engine_saw = seen(home, user_id, run_id)
    assert engine_saw["resume"].encode("latin-1") == PDF
    assert engine_saw["username"] == "username@example.com" and engine_saw["stop_before_submit"] is False
    assert alice.get("/api/usage").json()["data"]["applications"]["used"] == 1


def test_the_plan_limit_stops_a_live_run(db, setup, monkeypatch):
    alice, client, user_id, home = setup
    user = db.query(User).filter_by(email="alice@example.com").one()
    db.add(UsageCounter(user_id=user.id, period=current_period(), applications=8))
    db.commit()
    monkeypatch.setenv("STAND_IN_APPLY", "50")                       # would apply to everything
    run_id = alice.post("/api/automation/start", json={}, headers=csrf_headers(alice)).json()["data"]["id"]
    supervisor(client, home, user_id).run_once()

    run = run_view(alice, run_id)
    assert run["status"] == "cancelled" and run["stop_reason"] == "plan_limit"
    assert run["successful_count"] == 2
    assert alice.get("/api/usage").json()["data"]["applications"]["used"] == 10     # never past the limit
    logs = alice.get(f"/api/automation/{run_id}/logs").json()["data"]["items"]
    assert [i["event"] for i in logs].count("limit_reached") == 1
    assert logs[-1]["message"] == "Run stopped at this month's application limit."
    notes = alice.get("/api/notifications").json()["data"]["items"]
    assert [n["type"] for n in notes].count("limit_reached") == 1


def test_a_dry_run_and_an_engine_crash(db, setup, monkeypatch):
    alice, client, user_id, home = setup
    monkeypatch.setenv("STAND_IN_CRASH", "1")
    run_id = alice.post("/api/automation/start", json={"dry_run": True}, headers=csrf_headers(alice)).json()["data"]["id"]
    supervisor(client, home, user_id).run_once()

    assert seen(home, user_id, run_id)["stop_before_submit"] is True
    run = run_view(alice, run_id)
    assert run["status"] == "failed" and "exit code 3" in run["error_message"]
    assert supervisor(client, home, user_id).run_once() is False      # nothing left; no orphan complaints
    assert run_view(alice, run_id)["status"] == "failed"
