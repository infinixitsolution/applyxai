from backend.app.services.employment_ai_service import classify_employment, named_jobs
from backend.tests.conftest import csrf_headers


def test_named_jobs_require_a_company():
    rows = named_jobs(
        [
            {"title": "Devops engineer", "company": ""},
            {"title": "Intern", "company": "Infosys", "summary": "ServiceNow catalog."},
        ]
    )
    assert len(rows) == 1
    assert rows[0]["company"] == "Infosys"


def test_fresher_resume_is_classified_without_inventing_jobs():
    data = classify_employment(
        resume_text="Objective\nServiceNow Administrator fresher seeking a first full-time role.",
        work_history=[{"title": "Devops engineer", "company": ""}],
        experience_years=1,
    )
    assert data["kind"] == "fresher"
    assert data["status"] == "Fresher"
    assert data["experience_years"] == 0
    assert data["jobs"] == []


def test_experienced_resume_keeps_named_employer():
    data = classify_employment(
        resume_text="Experience\nDevOps Engineer at Acme 2020-2024",
        work_history=[{"title": "DevOps Engineer", "company": "Acme", "summary": "AWS."}],
        experience_years=4,
    )
    assert data["kind"] == "experienced"
    assert data["jobs"][0]["company"] == "Acme"


def test_fresher_keeps_named_internship():
    data = classify_employment(
        resume_text="MCA fresher. Internship at Infosys.",
        work_history=[{"title": "Intern", "company": "Infosys"}],
        experience_years=0,
    )
    assert data["kind"] == "fresher"
    assert data["jobs"][0]["company"] == "Infosys"


def test_employment_ai_fill_marks_fresher(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.employment_ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("employment-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "summary": "ServiceNow Administrator and ITSM Developer fresher",
            "skills": ["ServiceNow", "ITSM"],
            "experience_years": 1,
            "education": [{"school": "Administrative Management College", "degree": "MCA", "end_year": "2023"}],
            "work_history": [],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/sections/employment/ai-fill", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["kind"] == "fresher"
    assert body["status"] == "Fresher"
    assert body["experience_years"] == 0
    assert body["jobs"] == []
    saved = alice.get("/api/profile").json()["data"]
    assert saved["experience_years"] == 0
    assert saved["master"]["professional"]["employment_status"] == "Fresher"
    missing = [m["label"] for m in saved["completion"]["missing"]]
    assert "Employment history" not in missing
