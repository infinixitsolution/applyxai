import pytest

from backend.tests.conftest import csrf_headers


@pytest.fixture
def alice(make_user):
    return make_user()


def test_profile_returns_master_payload(alice):
    data = alice.get("/api/profile").json()["data"]
    assert "master" in data and "completion" in data
    assert isinstance(data["master"].get("common_answers"), list)


def test_automation_settings_round_trip(alice):
    h = csrf_headers(alice)
    snap = alice.get("/api/settings/automation").json()["data"]
    assert "pause_before_submit" in snap["values"]
    resp = alice.patch(
        "/api/settings/automation",
        json={"click_gap": 2, "pause_before_submit": True},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    values = alice.get("/api/settings/automation").json()["data"]["values"]
    assert values["click_gap"] == 2


def test_custom_questions_crud(alice):
    h = csrf_headers(alice)
    body = {
        "items": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "match": "contains",
                "pattern": "Have you used our internal product?",
                "answer": "No",
                "field_types": ["radio", "select"],
                "verified": True,
            }
        ]
    }
    resp = alice.put("/api/questions", json=body, headers=h)
    assert resp.status_code == 200, resp.text
    listed = alice.get("/api/questions").json()["data"]["items"]
    assert any("internal product" in q["pattern"] for q in listed)


def test_standard_experience_questions_are_hidden(alice):
    from backend.app.services.master_profile_service import _is_standard_human_pattern

    assert _is_standard_human_pattern("Please select your total years of professional experience:")
    assert _is_standard_human_pattern("Please select your total additional months of experience:")
    assert not _is_standard_human_pattern("Do you have professional experience building React applications in production?")


def test_custom_questions_sync_from_profile(make_user, monkeypatch):
    monkeypatch.setattr("backend.app.services.ai_service.ai_available", lambda *a, **k: False)
    alice = make_user("questions-sync@example.com")
    h = csrf_headers(alice)
    alice.put(
        "/api/profile",
        json={
            "first_name": "Shankar",
            "last_name": "Murthy",
            "current_title": "ServiceNow Administrator",
            "headline": "ServiceNow Administrator & ITSM Developer",
            "summary": "ServiceNow Administrator and ITSM Developer fresher.",
            "skills": ["ServiceNow", "ITSM"],
            "experience_years": 0,
            "education": [{"school": "Administrative Management College", "degree": "MCA", "end_year": "2023"}],
            "work_history": [],
            "current_company": "",
        },
        headers=h,
    )
    alice.patch(
        "/api/profile/sections/professional",
        json={"data": {"employment_status": "Fresher"}},
        headers=h,
    )
    alice.put(
        "/api/questions",
        json={
            "items": [
                {
                    "pattern": "Please select your total years of professional experience:",
                    "answer": "1 year",
                    "match": "contains",
                    "field_types": ["select"],
                },
                {
                    "pattern": "Please select your total additional months of experience:",
                    "answer": "12 months",
                    "match": "contains",
                    "field_types": ["select"],
                },
                {
                    "pattern": "Do you know anyone at PriceLabs?",
                    "answer": "No",
                    "match": "contains",
                    "field_types": ["radio"],
                },
                {
                    "pattern": "Do you know anyone at PriceLabs?",
                    "answer": "No",
                    "match": "contains",
                    "field_types": ["radio"],
                },
                {
                    "pattern": "Company",
                    "answer": "TechGlora Integrated IT Services",
                    "match": "contains",
                    "field_types": ["text"],
                },
                {
                    "pattern": "Your title",
                    "answer": "DevOps Engineer",
                    "match": "contains",
                    "field_types": ["text"],
                },
                {
                    "pattern": "Do you have professional experience building React applications in production?",
                    "answer": "no",
                    "match": "contains",
                    "field_types": ["radio"],
                },
            ]
        },
        headers=h,
    )
    resp = alice.post("/api/questions/sync-from-profile", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    patterns = [q["pattern"] for q in body["items"]]
    assert not any("years of professional experience" in p.lower() for p in patterns)
    assert not any("additional months" in p.lower() for p in patterns)
    assert patterns.count("Do you know anyone at PriceLabs?") == 1
    company = next(q for q in body["items"] if q["pattern"] == "Company")
    assert "techglora" not in company["answer"].lower()
    title = next(q for q in body["items"] if q["pattern"] == "Your title")
    assert "servicenow" in title["answer"].lower()
    assert "devops" not in title["answer"].lower()


def test_weak_custom_answers_are_queued_for_ai_fill():
    from backend.app.services.custom_questions_service import _should_ai_fill

    weak = {"pattern": "Which SaaS organisations have you worked with?", "answer": "I prefer not to guess.", "verified": False, "id": "1"}
    keep_pref = {"pattern": "Are you willing to take a drug test, in accordance with local law/regulations?", "answer": "Yes", "verified": False, "id": "2"}
    verified = {"pattern": "Company", "answer": "Acme", "verified": True, "id": "3"}
    know = {"pattern": "Do you know anyone at PriceLabs?", "answer": "No", "verified": False, "id": "4"}
    assert _should_ai_fill(weak, fresher=True) is True
    assert _should_ai_fill(keep_pref, fresher=True) is False
    assert _should_ai_fill(verified, fresher=True) is False
    assert _should_ai_fill(know, fresher=True) is False
