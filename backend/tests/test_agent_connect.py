"""One-click agent connect: start → approve (user) → poll (agent)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.conftest import csrf_headers


def test_connect_flow(app, make_user):
    agent = TestClient(app, raise_server_exceptions=False)
    user = make_user(client=TestClient(app, raise_server_exceptions=False))
    start = agent.post(
        "/api/agent/connect/start",
        json={"name": "Test PC", "platform": "pytest", "agent_version": "0.0-test"},
    )
    assert start.status_code == 201, start.text
    data = start.json()["data"]
    session_id = data["session_id"]
    secret = data["secret"]

    poll_before = agent.post(
        "/api/agent/connect/poll",
        json={"session_id": session_id, "secret": secret},
    )
    assert poll_before.status_code == 200
    assert poll_before.json()["data"]["status"] == "pending"

    approve = user.post(
        "/api/automation/devices/connect/approve",
        json={"session_id": session_id},
        headers=csrf_headers(user),
    )
    assert approve.status_code == 200, approve.text

    poll_after = agent.post(
        "/api/agent/connect/poll",
        json={"session_id": session_id, "secret": secret},
    )
    assert poll_after.status_code == 200
    body = poll_after.json()["data"]
    assert body["status"] == "ready"
    assert body["token"]
    assert body["device_id"]
    assert body["user_id"]
