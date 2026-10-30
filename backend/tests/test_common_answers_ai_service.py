from backend.app.services.common_answers_ai_service import heuristic_common_answers
from backend.tests.conftest import csrf_headers


def test_heuristic_fills_fresher_narratives_from_resume_facts():
    data = heuristic_common_answers(
        name="Shankar Murthy",
        title="ServiceNow Administrator",
        city="Bangalore",
        skills=["ServiceNow", "ITSM", "ITIL"],
        education=[{"degree": "MCA", "field": "Computer Applications", "school": "Administrative Management College", "end_year": "2023"}],
        work_history=[],
        roles=["ServiceNow Administrator", "ITSM Analyst"],
        locations=["Bangalore", "Remote"],
        experience_years=0,
        professional={"expected_ctc": 500000, "notice_period_days": 0, "availability_type": "Immediately"},
        engine={"legally_authorized": "Yes", "require_visa": "No"},
    )
    about = data["about_yourself"].lower()
    assert "shankar" in about
    assert "mca" in about
    assert "servicenow" in about
    assert "first full-time" in data["leaving_job"].lower()
    assert "relocate" in data["relocate"].lower() or "remote" in data["relocate"].lower()
    assert data["expected_salary"] == "500000"
    assert data["notice_period"] == "Immediate"
    assert data["when_join"] == "Immediately"
    assert data["work_auth"] == "Yes"
    assert data["visa_sponsor"] == "No"
    assert "employer" not in data["about_yourself"].lower()


def test_common_answers_ai_fill_skips_verified(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.common_answers_ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("common-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "skills": ["ServiceNow", "ITSM"],
            "preferred_roles": ["ServiceNow Administrator"],
            "preferred_locations": ["Bangalore"],
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
    seeded = alice.get("/api/profile").json()["data"]["master"]["common_answers"]
    locked = [{**row, "answer": "KEEP ME", "verified": True} if row.get("key") == "about_yourself" else row for row in seeded]
    patch = alice.patch("/api/profile/sections/common_answers", json={"data": locked}, headers=h)
    assert patch.status_code == 200, patch.text

    resp = alice.post("/api/profile/sections/common_answers/ai-fill", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["source"] == "heuristic"
    assert "about_yourself" in body["skipped_verified"]
    assert "about_yourself" not in body["filled"]
    assert len(body["filled"]) >= 3
    saved = {a["key"]: a for a in alice.get("/api/profile").json()["data"]["master"]["common_answers"]}
    assert saved["about_yourself"]["answer"] == "KEEP ME"
    assert "servicenow" in saved["why_role"]["answer"].lower()
    assert saved["why_hire"]["answer"].strip()
