from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.models import (
    AgentDevice, Application, AutomationJob, AutomationStatus, Notification, UsageCounter, User,
)
from backend.app.services.usage_service import current_period
from backend.tests.conftest import csrf_headers
from backend.tests.test_resumes_api import PDF


def e(kind, **fields):
    return {"event": kind, "ts": "2026-10-07T04:00:00+00:00", **fields}


def applied(job_id, title="Python Developer"):
    return e("applied", job_id=job_id, title=title, company="Acme", work_location="Pune", work_style="Hybrid",
             job_link=f"https://www.linkedin.com/jobs/view/{job_id}")


def make_ready(client):
    h = csrf_headers(client)
    assert client.put("/api/profile", json={"first_name": "Alice", "last_name": "Rao", "phone": "9876543210"},
                      headers=h).status_code == 200
    assert client.put("/api/preferences/search", json={"keywords": ["Python Developer"]}, headers=h).status_code == 200
    assert client.post("/api/resumes", files={"file": ("cv.pdf", PDF, "application/pdf")}, headers=h).status_code == 201
    return client


def pair(app, client, name="Work laptop"):
    code = client.post("/api/automation/devices/pairing-code", headers=csrf_headers(client)).json()["data"]["code"]
    agent = TestClient(app)                      # no cookies: the agent only ever has its device token
    resp = agent.post("/api/agent/pair", json={"code": code, "name": name, "platform": "Windows 10"})
    assert resp.status_code == 200, resp.text
    agent.headers["Authorization"] = f"Bearer {resp.json()['data']['token']}"
    return agent


@pytest.fixture
def alice(app, make_user):
    return make_ready(make_user("alice@example.com", client=TestClient(app)))


@pytest.fixture
def alice_agent(app, alice):
    return pair(app, alice)


def start(client, **body):
    return client.post("/api/automation/start", json=body, headers=csrf_headers(client))


def claim(agent):
    resp = agent.post("/api/agent/poll", json={})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["run"]


def post(agent, run_id, first_seq, events):
    return agent.post(f"/api/agent/runs/{run_id}/events", json={"first_seq": first_seq, "events": events})


def control(client, run_id, action):
    return client.post(f"/api/automation/{run_id}/{action}", headers=csrf_headers(client))


# ----------------------------------------------------------------------------- pairing
def test_pairing_code_is_single_use_and_the_token_is_only_shown_to_the_agent(app, alice, db):
    resp = alice.post("/api/automation/devices/pairing-code", headers=csrf_headers(alice))
    assert resp.status_code == 201
    code = resp.json()["data"]["code"]
    assert len(code) == 9 and code[4] == "-"

    agent = TestClient(app)
    paired = agent.post("/api/agent/pair", json={"code": code.lower().replace("-", " "), "name": "Laptop"})
    assert paired.status_code == 200
    token = paired.json()["data"]["token"]
    assert token.startswith("axd_")
    again = agent.post("/api/agent/pair", json={"code": code, "name": "Thief"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "INVALID_PAIRING_CODE"

    devices = alice.get("/api/automation/devices").json()["data"]["devices"]
    assert [(d["name"], d["online"]) for d in devices] == [("Laptop", True)]
    assert token not in alice.get("/api/automation").text
    stored = db.query(AgentDevice).one()
    assert stored.token_hash != token and token not in (stored.pairing_code_hash or "")


def test_expired_and_replaced_pairing_codes_are_refused(app, alice, db):
    first = alice.post("/api/automation/devices/pairing-code", headers=csrf_headers(alice)).json()["data"]["code"]
    second = alice.post("/api/automation/devices/pairing-code", headers=csrf_headers(alice)).json()["data"]["code"]
    agent = TestClient(app)
    assert agent.post("/api/agent/pair", json={"code": first}).json()["error"]["code"] == "INVALID_PAIRING_CODE"

    db.query(AgentDevice).update({"pairing_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    db.commit()
    assert agent.post("/api/agent/pair", json={"code": second}).json()["error"]["code"] == "INVALID_PAIRING_CODE"


def test_agent_endpoints_need_a_valid_device_token(app, alice, alice_agent):
    anonymous = TestClient(app)
    for method, url in [("post", "/api/agent/poll"), ("get", "/api/agent/me"),
                        ("post", f"/api/agent/runs/{'0' * 8}-0000-0000-0000-{'0' * 12}/events")]:
        resp = anonymous.request(method.upper(), url, json={"first_seq": 1, "events": []},
                                 headers={"Authorization": "Bearer axd_not-a-real-token"})
        assert resp.status_code == 401 and resp.json()["error"]["code"] == "DEVICE_UNAUTHORIZED"
    # A browser session is not a device token.
    assert alice.post("/api/agent/poll", json={}, headers=csrf_headers(alice)).status_code == 401

    device_id = alice.get("/api/automation/devices").json()["data"]["devices"][0]["id"]
    assert alice.delete(f"/api/automation/devices/{device_id}", headers=csrf_headers(alice)).status_code == 200
    assert alice_agent.post("/api/agent/poll", json={}).status_code == 401
    assert alice.get("/api/automation/devices").json()["data"]["devices"] == []


def test_logging_out_everywhere_disconnects_agents(alice, alice_agent):
    assert alice_agent.get("/api/agent/me").status_code == 200
    assert alice.post("/api/auth/logout-all", headers=csrf_headers(alice)).status_code == 200
    assert alice_agent.get("/api/agent/me").status_code == 401


def test_device_limit(app, alice, monkeypatch):
    from backend.app.services import agent_service
    monkeypatch.setattr(agent_service, "MAX_DEVICES", 1)
    pair(app, alice)
    resp = alice.post("/api/automation/devices/pairing-code", headers=csrf_headers(alice))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "DEVICE_LIMIT_REACHED"


# ----------------------------------------------------------------------------- starting
def test_start_explains_what_is_missing(app, make_user):
    bare = make_user("new@example.com", client=TestClient(app))
    resp = start(bare)
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "NOT_READY"
    problems = " ".join(resp.json()["error"]["details"])
    assert "phone" in problems.lower() and "resume" in problems.lower()
    overview = bare.get("/api/automation").json()["data"]
    assert overview["readiness"]["ready"] is False and overview["active"] is None


def test_start_needs_a_connected_agent_and_allows_one_run_at_a_time(app, alice):
    resp = start(alice)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "NO_AGENT"
    pair(app, alice)
    first = start(alice, dry_run=True)
    assert first.status_code == 201
    assert first.json()["data"]["status"] == "queued" and first.json()["data"]["dry_run"] is True
    second = start(alice)
    assert second.status_code == 409 and second.json()["error"]["code"] == "RUN_ACTIVE"


def test_start_refuses_when_the_monthly_limit_is_used_up(db, alice, alice_agent):
    user = db.query(User).filter_by(email="alice@example.com").one()
    db.add(UsageCounter(user_id=user.id, period=current_period(), applications=10))
    db.commit()
    resp = start(alice)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "PLAN_LIMIT_REACHED"


def test_stopping_a_run_no_agent_has_picked_up_cancels_it_at_once(alice, alice_agent):
    run_id = start(alice).json()["data"]["id"]
    resp = control(alice, run_id, "stop")
    assert resp.json()["data"]["status"] == "cancelled"
    assert claim(alice_agent) is None
    assert control(alice, run_id, "stop").json()["error"]["code"] == "RUN_FINISHED"


# ----------------------------------------------------------------------------- a run, end to end
def test_a_run_from_claim_to_finish(db, alice, alice_agent):
    run_id = start(alice).json()["data"]["id"]
    payload = claim(alice_agent)
    assert payload["id"] == run_id and payload["next_seq"] == 1 and payload["remaining_applications"] == 10
    assert payload["values"]["first_name"] == "Alice" and payload["values"]["search_terms"] == ["Python Developer"]
    assert payload["resume"]["file_type"] == "pdf"
    assert "password" not in str(payload["values"]).lower()
    busy = alice_agent.post("/api/agent/poll", json={"active_run_id": run_id}).json()["data"]
    assert busy["run"] is None
    assert alice_agent.get(f"/api/agent/runs/{run_id}/resume").content == PDF

    resp = post(alice_agent, run_id, 1, [e("run_started", search_terms=["Python Developer"]),
                                         e("job_started", job_id="101", title="Python Developer", company="Acme"),
                                         applied("101")])
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == {"next_seq": 4, "control": "run", "status": "running", "remaining_applications": 9}
    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["status"] == "running" and run["successful_count"] == 1

    assert control(alice, run_id, "pause").json()["data"]["control"] == "pause"
    assert post(alice_agent, run_id, 4, [e("paused")]).json()["data"]["control"] == "pause"
    assert alice.get(f"/api/automation/{run_id}").json()["data"]["status"] == "paused"
    assert control(alice, run_id, "resume").json()["data"]["control"] == "run"
    assert post(alice_agent, run_id, 5, [e("resumed")]).json()["data"]["control"] == "run"

    assert control(alice, run_id, "stop").json()["data"]["control"] == "stop"
    resp = post(alice_agent, run_id, 6, [e("skipped", job_id="102", reason="Filtered"),
                                         e("run_finished", applied=1, external=0, failed=0, skipped=1, stopped=True)])
    assert resp.json()["data"]["control"] == "stop" and resp.json()["data"]["status"] == "cancelled"

    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["status"] == "cancelled" and run["stop_reason"] == "user" and run["skipped_count"] == 1
    logs = alice.get(f"/api/automation/{run_id}/logs").json()["data"]
    assert logs["items"][0]["event"] == "claimed" and logs["items"][-1]["event"] == "run_finished"
    later = alice.get(f"/api/automation/{run_id}/logs", params={"after": logs["next_after"] - 1}).json()["data"]
    assert [i["event"] for i in later["items"]] == ["run_finished"]
    assert db.query(Notification).filter_by(type="run_finished").count() == 1
    assert control(alice, run_id, "pause").json()["error"]["code"] == "RUN_FINISHED"

    overview = alice.get("/api/automation").json()["data"]
    assert overview["active"] is None and overview["recent"][0]["id"] == run_id
    assert overview["agent_online"] is True and overview["usage"]["applications"]["used"] == 1


def test_retried_batches_are_applied_once_and_gaps_are_refused(db, alice, alice_agent):
    run_id = start(alice).json()["data"]["id"]
    claim(alice_agent)
    batch = [e("run_started"), applied("201"), applied("202")]
    assert post(alice_agent, run_id, 1, batch).json()["data"]["next_seq"] == 4
    assert post(alice_agent, run_id, 1, batch).json()["data"]["next_seq"] == 4          # whole batch again
    assert post(alice_agent, run_id, 3, [applied("202"), applied("203")]).json()["data"]["next_seq"] == 5  # overlap
    gap = post(alice_agent, run_id, 9, [applied("204")])
    assert gap.status_code == 409 and gap.json()["error"]["details"] == {"next_seq": 5}

    db.expire_all()
    assert db.query(Application).count() == 3
    assert db.query(UsageCounter).one().applications == 3
    assert alice.get(f"/api/automation/{run_id}").json()["data"]["successful_count"] == 3


def test_reaching_the_plan_limit_tells_the_agent_to_stop(db, alice, alice_agent):
    user = db.query(User).filter_by(email="alice@example.com").one()
    db.add(UsageCounter(user_id=user.id, period=current_period(), applications=9))
    db.commit()
    run_id = start(alice).json()["data"]["id"]
    assert claim(alice_agent)["remaining_applications"] == 1
    data = post(alice_agent, run_id, 1, [e("run_started"), applied("301")]).json()["data"]
    assert data["control"] == "stop" and data["remaining_applications"] == 0
    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["control"] == "stop" and run["stop_reason"] == "plan_limit"
    assert db.query(Notification).filter_by(type="limit_reached").count() == 1
    # Later batches don't add more warnings.
    post(alice_agent, run_id, 3, [e("job_started", job_id="302", title="Another")])
    assert db.query(Notification).filter_by(type="limit_reached").count() == 1


def test_a_run_fails_at_claim_if_setup_changed_since_start(db, alice, alice_agent):
    run_id = start(alice).json()["data"]["id"]
    resume_id = alice.get("/api/resumes").json()["data"]["resumes"][0]["id"]
    alice.delete(f"/api/resumes/{resume_id}", headers=csrf_headers(alice))
    assert claim(alice_agent) is None
    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["status"] == "failed" and "resume" in run["error_message"].lower()


def test_an_agent_that_restarts_mid_run_fails_the_run_it_lost(alice, alice_agent):
    run_id = start(alice).json()["data"]["id"]
    claim(alice_agent)
    post(alice_agent, run_id, 1, [e("run_started")])
    busy = alice_agent.post("/api/agent/poll", json={"active_run_id": run_id})
    assert busy.json()["data"]["run"] is None
    assert alice.get(f"/api/automation/{run_id}").json()["data"]["status"] == "running"
    assert claim(alice_agent) is None                                # restarted: no longer reports the run
    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["status"] == "failed" and "restarted" in run["error_message"]


def test_late_events_for_a_finished_run_are_still_saved_but_the_agent_is_told_to_stop(db, alice, alice_agent):
    run_id = start(alice).json()["data"]["id"]
    claim(alice_agent)
    db.query(AutomationJob).update({"last_seen_at": datetime.now(timezone.utc) - timedelta(minutes=10)})
    db.commit()
    assert alice.get("/api/automation").json()["data"]["active"] is None             # reaped on page load
    data = post(alice_agent, run_id, 1, [applied("401")]).json()["data"]
    assert data["control"] == "stop" and data["status"] == "failed"
    db.expire_all()
    assert db.query(Application).one().status.value == "applied"


# ----------------------------------------------------------------------------- isolation
def test_users_and_their_agents_cannot_touch_each_others_runs(app, make_user, alice, alice_agent):
    bob = make_ready(make_user("bob@example.com", client=TestClient(app)))
    bob_agent = pair(app, bob, "Bob's PC")
    run_id = start(alice).json()["data"]["id"]

    assert claim(bob_agent) is None                                  # Bob's agent never sees Alice's run
    for action in ("pause", "resume", "stop"):
        assert control(bob, run_id, action).status_code == 404
    assert bob.get(f"/api/automation/{run_id}").status_code == 404
    assert bob.get(f"/api/automation/{run_id}/logs").status_code == 404
    assert bob.get("/api/automation").json()["data"]["active"] is None

    claim(alice_agent)
    assert bob_agent.get(f"/api/agent/runs/{run_id}/resume").status_code == 404
    assert post(bob_agent, run_id, 1, [applied("999")]).status_code == 404
    alice_device = alice.get("/api/automation/devices").json()["data"]["devices"][0]["id"]
    assert bob.delete(f"/api/automation/devices/{alice_device}", headers=csrf_headers(bob)).status_code == 404


# ----------------------------------------------------------------------------- maintenance
def test_the_reaper_fails_silent_runs_and_cancels_unclaimed_ones(db, alice, alice_agent, monkeypatch):
    from backend.app import worker
    run_id = start(alice).json()["data"]["id"]
    claim(alice_agent)
    old = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.query(AutomationJob).update({"last_seen_at": old})
    db.commit()

    monkeypatch.setattr(worker, "SessionLocal", sessionmaker(bind=db.get_bind(), expire_on_commit=False))
    assert worker.reap_stale_runs() == 1
    run = alice.get(f"/api/automation/{run_id}").json()["data"]
    assert run["status"] == "failed" and "Lost contact" in run["error_message"]

    user = db.query(User).filter_by(email="alice@example.com").one()
    stale_queue = AutomationJob(user_id=user.id, status=AutomationStatus.QUEUED,
                                created_at=datetime.now(timezone.utc) - timedelta(hours=25))
    db.add(stale_queue)
    db.commit()
    assert worker.reap_stale_runs() == 1
    db.expire_all()
    assert db.get(AutomationJob, stale_queue.id).status == AutomationStatus.CANCELLED
    assert worker.reap_stale_runs() == 0


def test_celery_schedules_the_housekeeping_tasks():
    from backend.app.worker import celery_app
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert scheduled == {
        "applyxai.reap_stale_runs",
        "applyxai.delete_expired_pairings",
        "applyxai.send_candidate_daily_reports",
    }
    assert scheduled <= set(celery_app.tasks)
