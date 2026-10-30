from backend.app.services.skills_ai_service import categorize_skill, resume_mentions, skills_from_resume
from backend.app.services.resume_text_service import guess_skills_from_text
from backend.tests.conftest import csrf_headers

RESUME = """
SHANKAR MURTHY S
Objective
Motivated ServiceNow Administrator and ITSM Developer fresher.
Technical Skills
• ServiceNow: ITSM, System Administration, Service Catalog, Knowledge Management
• ITSM: Incident, Problem, Change, Request Management
• Database: Basic SQL
Education
• MCA (2023), Administrative Management College, Bangalore
Languages
• English, Kannada, Telugu
"""


def test_guess_skills_stays_in_skills_section():
    names = [s.lower() for s in guess_skills_from_text(RESUME, [])]
    assert "servicenow" in names
    assert "itsm" in names
    assert "sql" in names
    assert "incident management" in names
    assert "bangalore" not in names
    assert "english" not in names
    assert "mca (2023)" not in names
    assert "education" not in names


def test_skills_from_resume_drops_tools_not_on_resume():
    rows = skills_from_resume(RESUME, extra=["Devops", "kubernet", "AWS", "ServiceNow"])
    names = [r["name"].lower() for r in rows]
    assert "servicenow" in names
    assert "aws" not in names
    assert "devops" not in names
    assert "kubernetes" not in names
    assert any(r["category"] == "Business applications" for r in rows if r["name"] == "ServiceNow")
    assert categorize_skill("SQL") == "Databases"


def test_resume_mentions_requires_evidence():
    assert resume_mentions("ServiceNow", RESUME) is True
    assert resume_mentions("Incident Management", RESUME) is True
    assert resume_mentions("AWS", RESUME) is False
    assert resume_mentions("Kubernetes", RESUME) is False


def test_skills_ai_fill_replaces_invented_quick_skills(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.skills_ai_service.ai_available", lambda *a, **k: False)
    monkeypatch.setattr("backend.app.services.skills_ai_service._resume_text", lambda db, uid: RESUME)
    alice = make_user("skills-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "skills": ["Devops", "kubernet", "AWS"],
            "experience_years": 0,
            "education": [{"school": "Administrative Management College", "degree": "MCA", "end_year": "2023"}],
            "work_history": [],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/sections/skills/ai-fill", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    names = [s.lower() for s in body["skills"]]
    assert "servicenow" in names
    assert "itsm" in names
    assert "aws" not in names
    assert "devops" not in names
    saved = alice.get("/api/profile").json()["data"]
    assert "ServiceNow" in saved["skills"]
    master_names = [str(r.get("name") or "") for r in saved["master"]["skills"]]
    assert "ServiceNow" in master_names
    assert all(str(r.get("category") or "") for r in saved["master"]["skills"])
    missing = [m["label"] for m in saved["completion"]["missing"]]
    assert "Skills" not in missing
