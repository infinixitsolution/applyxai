from backend.app.services.career_ai_service import heuristic_career_preferences
from backend.tests.conftest import csrf_headers


def test_heuristic_expands_devops_and_bangalore():
    data = heuristic_career_preferences(
        title="Devops engineer",
        skills=["Devops", "kubernet", "AWS", "ServiceNow"],
        roles=["Devops"],
        locations=["Bangalore"],
        city="Bangalore",
    )
    roles = " ".join(data["preferred_roles"]).lower()
    assert "devops engineer" in roles
    assert "cloud engineer" in roles
    assert "servicenow" in roles
    locs = " ".join(data["preferred_locations"]).lower()
    assert "bangalore" in locs
    assert "bengaluru" in locs
    assert "remote" in locs


def test_career_ai_enhance_endpoint_fills_roles(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.career_ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("career-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "Devops engineer",
            "skills": ["Devops", "AWS", "ServiceNow"],
            "preferred_roles": ["Devops"],
            "preferred_locations": ["Bangalore"],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/sections/career/ai-enhance", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["source"] in ("ai", "heuristic")
    assert any("DevOps" in r or "devops" in r.lower() for r in body["preferred_roles"])
    assert len(body["preferred_roles"]) >= 2
    assert any("Bangalore" in loc or "Bengaluru" in loc for loc in body["preferred_locations"])
    saved = alice.get("/api/profile").json()["data"]
    assert saved["preferred_roles"]
    assert saved["preferred_locations"]
