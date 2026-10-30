from backend.tests.conftest import csrf_headers


def _no_ai(*_a, **_k):
    return False


def test_profile_ai_enhance_fills_resume_sections_without_inventing_jobs(make_user, monkeypatch):
    for mod in (
        "backend.app.services.professional_ai_service",
        "backend.app.services.projects_ai_service",
        "backend.app.services.career_ai_service",
        "backend.app.services.common_answers_ai_service",
        "backend.app.services.screening_ai_service",
        "backend.app.services.resume_ai_service",
        "backend.app.services.employment_ai_service",
        "backend.app.services.skills_ai_service",
    ):
        monkeypatch.setattr(f"{mod}.ai_available", _no_ai)

    alice = make_user("profile-enhance@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "headline": "x",
            "summary": "ServiceNow Administrator and ITSM Developer fresher",
            "skills": ["ServiceNow", "ITSM"],
            "experience_years": 1,
            "preferred_roles": ["ServiceNow Administrator"],
            "preferred_locations": ["Bangalore"],
            "education": [{"school": "Administrative Management College", "degree": "MCA", "end_year": "2023"}],
            "work_history": [],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/ai-enhance", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["percent"] < 100
    labels = [m["label"] for m in body["missing"]]
    assert "Employment history" not in labels
    assert "Accomplishments or links" not in labels
    assert "Profile photo" in labels
    assert not body["profile"]["work_history"]
    assert body["profile"]["experience_years"] == 0
    assert body["profile"]["master"]["professional"]["employment_status"] == "Fresher"
    assert body["profile"]["summary"]
    assert "servicenow" in body["profile"]["summary"].lower() or "itsm" in body["profile"]["summary"].lower()
    step_ids = {s["id"]: s for s in body["steps"]}
    assert step_ids["employment"]["ok"] is True
    assert step_ids["skills"]["ok"] is True
    assert step_ids["professional"]["ok"] is True
    assert step_ids["career"]["ok"] is True
    assert step_ids["projects"]["ok"] is True
    assert any(m.get("hint") for m in body["missing"])
    assert any(m.get("ai") is False for m in body["missing"])
