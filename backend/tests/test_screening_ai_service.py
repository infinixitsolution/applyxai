from backend.app.services.screening_ai_service import heuristic_screening_answers
from backend.tests.conftest import csrf_headers


def test_heuristic_builds_background_from_resume_facts():
    data = heuristic_screening_answers(
        name="Shankar Murthy",
        title="ServiceNow Administrator",
        city="Bangalore",
        skills=["ServiceNow", "ITSM"],
        education=[{"degree": "MCA", "field": "Computer Applications", "school": "Administrative Management College", "end_year": "2023"}],
        work_history=[],
        roles=["ServiceNow Administrator"],
        experience_years=0,
        professional={"expected_ctc": 500000, "current_ctc": 400000, "notice_period_days": 0},
        personal={"city": "Bangalore", "country": "India"},
        engine={},
    )
    facts = data["user_information_all"].lower()
    assert "servicenow" in facts
    assert "mca" in facts
    assert "bangalore" in facts
    assert "cover_letter" in data
    assert "hiring manager" in data["cover_letter"].lower()
    assert data["years_of_experience"] == "0"
    assert data["desired_salary"] == 500000
    assert "require_visa" not in data
    assert "legally_authorized" not in data


def test_screening_ai_fill_writes_background(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.screening_ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("screening-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "skills": ["ServiceNow", "ITSM"],
            "preferred_roles": ["ServiceNow Administrator"],
            "experience_years": 0,
            "education": [
                {
                    "school": "Administrative Management College",
                    "degree": "MCA",
                    "field": "Computer Applications",
                    "end_year": "2023",
                }
            ],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/sections/screening/ai-fill", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["source"] == "heuristic"
    assert "user_information_all" in body["filled"]
    text = str(body["answers"]["user_information_all"]).lower()
    assert "servicenow" in text
    saved = alice.get("/api/preferences/application").json()["data"]
    assert "servicenow" in str(saved["answers"].get("user_information_all") or "").lower()
    assert saved.get("user_information_all")
