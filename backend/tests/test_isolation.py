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


def test_one_users_csrf_token_does_not_work_for_another(two_users):
    alice, bob = two_users
    resp = bob.put("/api/profile", json={}, headers=csrf_headers(alice))
    assert resp.status_code == 403
