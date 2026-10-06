"""One user must never read or change another user's data, even with a valid ID."""

import pytest
from fastapi.testclient import TestClient

from backend.tests.conftest import csrf_headers
from backend.tests.test_resumes_api import PDF


@pytest.fixture
def two_users(app, make_user):
    alice = make_user("alice@example.com", client=TestClient(app))
    bob = make_user("bob@example.com", client=TestClient(app))
    return alice, bob


def test_resumes_are_private(two_users):
    alice, bob = two_users
    resp = alice.post("/api/resumes", files={"file": ("alice.pdf", PDF, "application/pdf")},
                      headers=csrf_headers(alice))
    rid = resp.json()["data"]["id"]

    assert bob.get("/api/resumes").json()["data"]["resumes"] == []
    h = csrf_headers(bob)
    for method, url, kwargs in [
        ("get", f"/api/resumes/{rid}/download", {}),
        ("patch", f"/api/resumes/{rid}", {"json": {"name": "mine now"}}),
        ("post", f"/api/resumes/{rid}/default", {}),
        ("delete", f"/api/resumes/{rid}", {}),
    ]:
        resp = getattr(bob, method)(url, headers=h, **kwargs)
        assert resp.status_code == 404, (method, url, resp.text)     # 404, not 403: don't confirm it exists

    listed = alice.get("/api/resumes").json()["data"]["resumes"]
    assert listed[0]["name"] == "alice" and listed[0]["is_default"] is True
    assert alice.get(f"/api/resumes/{rid}/download").content == PDF


def test_profile_and_preferences_are_private(two_users):
    alice, bob = two_users
    ha = csrf_headers(alice)
    alice.put("/api/profile", json={"first_name": "Alice", "headline": "Secret headline"}, headers=ha)
    alice.put("/api/preferences/search", json={"keywords": ["Alice role"]}, headers=ha)
    alice.patch("/api/preferences/application", json={"desired_salary": 999}, headers=ha)

    assert bob.get("/api/profile").json()["data"]["headline"] is None
    assert bob.get("/api/preferences/search").json()["data"]["configured"] is False
    assert bob.get("/api/preferences/application").json()["data"] == {}

    hb = csrf_headers(bob)
    bob.put("/api/preferences/search", json={"keywords": ["Bob role"]}, headers=hb)
    assert alice.get("/api/preferences/search").json()["data"]["keywords"] == ["Alice role"]


def test_applications_jobs_and_stats_are_private(two_users, db):
    alice, bob = two_users
    from backend.app.models import ApplicationStatus
    from backend.tests.factories import add_application

    mine = add_application(db, "alice@example.com", "100", title="Alice-only job")
    shared_a = add_application(db, "alice@example.com", "200", title="Shared job")
    shared_b = add_application(db, "bob@example.com", "200", ApplicationStatus.FAILED, title="Shared job")
    assert shared_a.job_id == shared_b.job_id

    assert bob.get(f"/api/applications/{mine.id}").status_code == 404
    assert bob.get(f"/api/applications/{shared_a.id}").status_code == 404
    assert bob.get(f"/api/jobs/{mine.job_id}").status_code == 404           # never encountered it

    # The shared job is visible to Bob, but only with Bob's own application on it.
    job = bob.get(f"/api/jobs/{shared_b.job_id}").json()["data"]
    assert job["application"]["id"] == str(shared_b.id) and job["application"]["status"] == "failed"

    bob_apps = bob.get("/api/applications").json()["data"]
    assert [a["id"] for a in bob_apps["items"]] == [str(shared_b.id)]
    assert [j["title"] for j in bob.get("/api/jobs?q=job").json()["data"]["items"]] == ["Shared job"]
    assert "Alice-only" not in bob.get("/api/applications/export").text

    bob_stats = bob.get("/api/dashboard/stats").json()["data"]
    assert bob_stats["total_applied"] == 0 and bob_stats["applications_by_status"]["failed"] == 1
    assert bob.get("/api/usage").json()["data"]["applications"]["used"] == 0
    assert alice.get("/api/usage").json()["data"]["applications"]["used"] == 2


def test_notifications_are_private(two_users, db):
    alice, bob = two_users
    from backend.app.services import notification_service
    from backend.tests.factories import user_id

    note = notification_service.notify(db, user_id(db, "alice@example.com"), "run_finished", "Alice's run")
    db.commit()
    assert bob.get("/api/notifications").json()["data"]["total"] == 0
    assert bob.post(f"/api/notifications/{note.id}/read", headers=csrf_headers(bob)).status_code == 404
    assert bob.post("/api/notifications/read-all", headers=csrf_headers(bob)).json()["data"] == {"marked": 0}
    assert alice.get("/api/notifications").json()["data"]["unread_count"] == 1


def test_one_users_csrf_token_does_not_work_for_another(two_users):
    alice, bob = two_users
    resp = bob.put("/api/profile", json={}, headers=csrf_headers(alice))
    assert resp.status_code == 403
