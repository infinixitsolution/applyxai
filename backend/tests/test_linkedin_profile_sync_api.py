"""LinkedIn profile sync API and mapping."""

from backend.app.services import linkedin_profile_sync_service as lp_sync
from backend.tests.conftest import csrf_headers


def test_profile_sync_readiness_requires_linkedin_url(make_user):
    alice = make_user("sync@example.com")
    r = alice.get("/api/automation/profile-sync/readiness")
    assert r.status_code == 200
    assert r.json()["data"]["ready"] is False


def test_profile_sync_start_without_agent_returns_409(make_user, db):
    alice = make_user("sync2@example.com")
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
    r = alice.post("/api/automation/profile-sync/start", json={"dry_run": True}, headers=h)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "NOT_READY"


def test_sync_plan_returns_fill_actions(make_user):
    alice = make_user("sync3@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={"first_name": "Ada", "last_name": "Lovelace", "phone": "9876543210", "headline": "Engineer"},
        headers=h,
    )
    r = alice.get("/api/profile/linkedin/sync-plan")
    assert r.status_code == 200
    plan = r.json()["data"]["plan"]
    assert any(p["section"] == "headline" for p in plan)


def test_build_snapshot_skills(db):
    from backend.app.models import User, UserProfile

    user = User(email="snap@example.com", password_hash="x", is_verified=True, first_name="A", last_name="B")
    user.profile = UserProfile(
        phone="1234567890",
        headline="H",
        work_history=[{"title": "T", "company": "C", "start": "2020"}],
        education=[{"school": "S", "degree": "D", "start_year": "2018"}],
        skills=["Python"],
        master_data={"career": {"linkedin_url": "https://linkedin.com/in/x"}, "skills": [{"name": "Go"}]},
    )
    snap = lp_sync.build_snapshot(db, user)
    assert snap["headline"] == "H"
    assert len(snap["skills"]) >= 2
