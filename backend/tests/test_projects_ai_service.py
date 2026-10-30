from backend.app.services.projects_ai_service import (
    fresher_academic_fallback,
    heuristic_projects,
    parse_project_lines,
    projects_from_work_history,
)
from backend.tests.conftest import csrf_headers


def test_parse_academic_projects_section():
    lines = [
        "ServiceNow Incident Portal",
        "Built an incident catalog and workflow on ServiceNow.",
        "ITSM Knowledge Base",
        "Created knowledge articles for request fulfillment.",
    ]
    rows = parse_project_lines(lines, skills=["ServiceNow", "ITSM"])
    titles = [r["title"].lower() for r in rows]
    assert any("incident" in t for t in titles)
    assert any("knowledge" in t for t in titles)
    assert "ServiceNow" in rows[0]["technologies"]


def test_work_history_becomes_professional_projects():
    rows = projects_from_work_history(
        [
            {
                "title": "DevOps Engineer",
                "company": "Acme",
                "summary": "Automated Kubernetes deploys with AWS.",
            }
        ],
        skills=["Kubernetes", "AWS"],
    )
    assert rows[0]["title"] == "DevOps Engineer at Acme"
    assert "Kubernetes" in rows[0]["technologies"]


def test_fresher_without_projects_section_uses_academic_fallback():
    suggested, kind = heuristic_projects(
        resume_text="SHANKAR MURTHY\nEducation\nMCA 2023 Administrative Management College\nSkills\nServiceNow, ITSM",
        work_history=[],
        skills=["ServiceNow", "ITSM"],
        education=[{"degree": "MCA", "school": "Administrative Management College", "end_year": "2023"}],
        title="ServiceNow Administrator",
    )
    assert kind == "academic"
    assert suggested
    assert "servicenow" in suggested[0]["title"].lower()
    assert suggested[0]["role"] == "Student"


def test_experienced_prefers_employment_when_no_project_heading():
    suggested, kind = heuristic_projects(
        resume_text="Jane Doe\nExperience\nDevOps Engineer at Acme 2020-2024",
        work_history=[{"title": "DevOps Engineer", "company": "Acme", "summary": "Ran AWS pipelines."}],
        skills=["AWS"],
    )
    assert kind == "professional"
    assert any("Acme" in p["title"] for p in suggested)


def test_projects_ai_fill_endpoint_adds_academic_for_fresher(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.projects_ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("projects-ai@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "skills": ["ServiceNow", "ITSM"],
            "experience_years": 0,
            "education": [
                {
                    "school": "Administrative Management College",
                    "degree": "MCA",
                    "end_year": "2023",
                }
            ],
            "work_history": [],
        },
        headers=h,
    )
    resp = alice.post("/api/profile/sections/projects/ai-fill", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["kind"] == "academic"
    assert body["added"]
    saved = alice.get("/api/profile").json()["data"]["master"]["projects"]
    assert saved and saved[0]["title"]
    assert fresher_academic_fallback(skills=["ServiceNow"], education=[{"degree": "MCA"}])
