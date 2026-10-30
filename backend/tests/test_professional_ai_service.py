from backend.app.services.professional_ai_service import heuristic_professional_overview
from backend.tests.conftest import csrf_headers

RESUME = """
SHANKAR MURTHY S
Objective
Motivated and detail-oriented ServiceNow Administrator and ITSM Developer fresher
with hands-on knowledge of the ServiceNow platform, IT Service Management processes,
and application development.
Technical Skills
ServiceNow, ITSM, Incident Management
Education
MCA (2023), Administrative Management College, Bangalore
"""


def test_heuristic_uses_resume_objective_for_summary():
    data = heuristic_professional_overview(
        resume_text=RESUME,
        title="Devlops engineer",
        city="Bangalore",
        skills=["Devops", "ServiceNow", "ITSM"],
        education=[{"degree": "MCA", "school": "Administrative Management College", "end_year": "2023"}],
        work_history=[],
        experience_years=0,
    )
    assert "servicenow" in data["summary"].lower()
    assert "fresher" in data["summary"].lower() or "servicenow" in data["headline"].lower()
    assert "acme" not in data["summary"].lower()
    assert "servicenow" in data["headline"].lower() or "itsm" in data["headline"].lower()


def test_professional_ai_complete_writes_summary(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.professional_ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("pro-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "headline": "x",
            "summary": "",
            "skills": ["ServiceNow", "ITSM"],
            "experience_years": 0,
            "education": [{"school": "Administrative Management College", "degree": "MCA", "end_year": "2023"}],
            "work_history": [],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/sections/professional/ai-complete", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert "summary" in body["filled"]
    assert body["summary"].strip()
    saved = alice.get("/api/profile").json()["data"]
    assert saved["summary"]
