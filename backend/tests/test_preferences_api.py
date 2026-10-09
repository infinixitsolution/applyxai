import pytest

from backend.tests.conftest import csrf_headers

SEARCH = {
    "keywords": ["Python Developer", " python developer ", "Backend Engineer"],
    "location": "Bengaluru, India",
    "easy_apply_only": True,
    "experience_level": ["Entry level", "Associate"],
    "job_type": ["Full-time", "Contract"],
    "on_site": ["Remote", "Hybrid"],
    "companies": [],
    "date_posted": "Past week",
    "sort_by": "Most recent",
    "salary_min": 500000,
    "salary_max": 1500000,
    "extra": {"current_experience": 3, "bad_words": ["unpaid"], "skip_non_sponsoring_jobs": False},
}


@pytest.fixture
def alice(make_user):
    return make_user()


# --- profile ----------------------------------------------------------------------------

def test_profile_starts_empty_and_round_trips(alice):
    data = alice.get("/api/profile").json()["data"]
    assert data["email"] == "alice@example.com" and data["skills"] == []

    body = {"first_name": "Alice", "last_name": "Smith", "phone": "+91 98765 43210", "headline": "Engineer",
            "summary": "Builds things.", "current_title": "SDE", "current_company": "Acme",
            "experience_years": 4, "skills": ["Python", "python", " SQL "], "preferred_roles": ["Backend"],
            "preferred_locations": ["Remote"]}
    resp = alice.put("/api/profile", json=body, headers=csrf_headers(alice))
    assert resp.status_code == 200, resp.text
    data = alice.get("/api/profile").json()["data"]
    assert data["first_name"] == "Alice" and data["experience_years"] == 4
    assert data["skills"] == ["Python", "SQL"]                    # trimmed and de-duplicated
    assert alice.get("/api/auth/me").json()["data"]["user"]["first_name"] == "Alice"


@pytest.mark.parametrize("patch", [
    {"phone": "call me maybe"},
    {"experience_years": -1},
    {"experience_years": 99},
    {"skills": ["x" * 101]},
    {"unknown_field": 1},
])
def test_profile_rejects_invalid_input(alice, patch):
    resp = alice.put("/api/profile", json=patch, headers=csrf_headers(alice))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_profile_requires_csrf_and_login(alice, api, app):
    assert alice.put("/api/profile", json={}).status_code == 403
    from fastapi.testclient import TestClient
    assert TestClient(app).get("/api/profile").status_code == 401


# --- search preferences -----------------------------------------------------------------

def test_search_preferences_round_trip(alice):
    empty = alice.get("/api/preferences/search").json()["data"]
    assert empty["configured"] is False and empty["keywords"] == [] and empty["easy_apply_only"] is True
    resp = alice.put("/api/preferences/search", json=SEARCH, headers=csrf_headers(alice))
    assert resp.status_code == 200, resp.text
    data = alice.get("/api/preferences/search").json()["data"]
    assert data["configured"] is True
    assert data["keywords"] == ["Python Developer", "Backend Engineer"]
    assert data["experience_level"] == ["Entry level", "Associate"]
    assert data["extra"]["current_experience"] == 3


@pytest.mark.parametrize("patch", [
    {"experience_level": ["1"]},                       # numeric LinkedIn codes are not engine values
    {"experience_level": ["entry level"]},             # exact case matters (filters are clicked by text)
    {"job_type": ["permanent"]},
    {"job_type": "Full-time"},                         # must be a list
    {"on_site": ["Work from home"]},
    {"date_posted": "Yesterday"},
    {"sort_by": "Newest"},
    {"keywords": []},
    {"keywords": ["   "]},
    {"salary_min": 10, "salary_max": 5},
    {"salary_min": -1},
    {"extra": {"switch_number": 0}},
    {"extra": {"current_experience": "3"}},
    {"extra": {"randomize_search_order": "yes"}},
    {"extra": {"not_a_setting": True}},
    {"extra": {"search_terms": ["x"]}},                # column-backed keys can't sneak in via extra
    {"unexpected": 1},
])
def test_search_rejects_values_the_engine_would_reject(alice, patch):
    resp = alice.put("/api/preferences/search", json={**SEARCH, **patch}, headers=csrf_headers(alice))
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_options_endpoint_exposes_engine_strings(alice):
    data = alice.get("/api/preferences/options").json()["data"]
    assert data["search"]["experience_level"][1] == "Entry level"
    assert "Full-time" in data["search"]["job_type"]
    keys = {f["key"] for f in data["application_fields"]}
    assert {"ethnicity", "desired_salary", "cover_letter"} <= keys
    assert not keys & {"password", "username", "llm_api_key", "default_resume_path", "first_name"}
    ethnicity = next(f for f in data["application_fields"] if f["key"] == "ethnicity")
    assert "" not in ethnicity["options"]                    # the engine validator rejects ""


# --- application preferences ------------------------------------------------------------

def test_application_preferences_merge_and_reset(alice):
    h = csrf_headers(alice)
    resp = alice.patch("/api/preferences/application",
                       json={"desired_salary": 1200000, "require_visa": "No", "cover_letter": "Hi"}, headers=h)
    assert resp.status_code == 200, resp.text
    resp = alice.patch("/api/preferences/application", json={"notice_period": 30, "cover_letter": None}, headers=h)
    assert resp.json()["data"]["answers"] == {"desired_salary": 1200000, "require_visa": "No", "notice_period": 30}
    assert alice.get("/api/preferences/application").json()["data"]["answers"]["notice_period"] == 30


@pytest.mark.parametrize("body,field", [
    ({"desired_salary": -5}, "desired_salary"),
    ({"desired_salary": "lots"}, "desired_salary"),
    ({"desired_salary": True}, "desired_salary"),
    ({"ethnicity": ""}, "ethnicity"),
    ({"gender": "M"}, "gender"),
    ({"require_visa": "Maybe"}, "require_visa"),
    ({"click_gap": 1.5}, "click_gap"),
    ({"password": "hunter2"}, "password"),            # secrets are never stored server-side
    ({"llm_api_key": "sk-x"}, "llm_api_key"),
    ({"default_resume_path": "C:/x.pdf"}, "default_resume_path"),
])
def test_application_preferences_reject_invalid(alice, body, field):
    resp = alice.patch("/api/preferences/application", json=body, headers=csrf_headers(alice))
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and err["details"][0]["field"] == field
    assert alice.get("/api/preferences/application").json()["data"]["answers"] == {}


def test_resolve_pending_saves_human_questions(alice, db):
    from backend.app.models import User
    from backend.app.services import preferences_service

    h = csrf_headers(alice)
    row = db.query(User).filter_by(email="alice@example.com").one()
    preferences_service.capture_form_question(
        db,
        row.id,
        {"label": "Years of Kubernetes?", "question_type": "text", "needs_answer": True},
        {"title": "SRE", "company": "Acme"},
    )
    db.commit()
    doc = alice.get("/api/preferences/application").json()["data"]
    assert len(doc["pending_form_questions"]) == 1
    qid = doc["pending_form_questions"][0]["id"]
    resp = alice.post(
        "/api/preferences/application/resolve-pending",
        json={"answers": [{"id": qid, "answer": "5 years"}]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["pending_form_questions"]) == 1
    assert data["pending_form_questions"][0]["needs_answer"] is False
    assert data["pending_form_questions"][0].get("has_saved_rule") is True
    assert any(hq["pattern"] == "Years of Kubernetes?" and hq["answer"] == "5 years" for hq in data["human_questions"])
