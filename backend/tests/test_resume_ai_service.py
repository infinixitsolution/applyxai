from backend.app.services import resume_text_service
from backend.app.models import Resume, User, UserProfile
from backend.app.services.resume_ai_service import (
    build_resume_version_name,
    humanize_tailor_patch,
    master_skills_ready,
    match_score,
    persist_master_skills_from_profile,
    validate_tailor_patch,
)


def test_heuristic_intake_finds_name_phone_and_summary():
    text = (
        "Jane Doe\n"
        "+91 9876543210\n\n"
        "Summary\n"
        "Backend engineer building APIs with Python and Django.\n\n"
        "Experience\n"
        "Software Engineer\n"
        "Acme Corp\n"
        "2020 - Present\n"
    )
    data = resume_text_service.heuristic_profile_intake(text)
    assert data["first_name"] == "Jane" and data["last_name"] == "Doe"
    assert data["phone"]
    assert "Python" in (data["summary"] or "")
    assert data["current_title"]
    assert data["cover_letter"]


def test_match_score_gate():
    masters = ["python", "django", "postgresql"]
    text = "Built APIs with Python and Django"
    jd = "Looking for Python Django PostgreSQL experience"
    score, missing = match_score(masters, text, jd)
    assert score >= 50
    assert "python" not in missing


def test_build_resume_version_name(db):
    from backend.app.models import User, UserProfile

    user = User(
        email="ada@example.com",
        password_hash="x",
        first_name="Ada",
        last_name="Lovelace",
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, experience_years=5))
    db.commit()
    name = build_resume_version_name(
        db,
        user,
        master_skills=["Python", "Django"],
        patch={"skills_order": ["Django", "Python"]},
    )
    assert name == "Ada Lovelace_Django_5 years"


def test_humanize_strips_ai_buzzwords():
    assert "passionate" not in resume_text_service.humanize_line(
        "Passionate results-driven engineer eager to leverage synergies."
    ).lower()


def test_humanize_tailor_patch_cleans_summary():
    patch = humanize_tailor_patch(
        {"summary_lines": ["Results-driven Python developer."], "skills_order": ["Python"]}
    )
    assert "results-driven" not in patch["summary_lines"][0].lower()


def test_master_skills_ready_uses_profile_when_resume_empty(db):
    user = User(email="skills@example.com", password_hash="x", is_verified=True)
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, skills=["Python", "SQL"]))
    resume = Resume(
        user_id=user.id,
        name="Main",
        filename="m.pdf",
        storage_path="resumes/test/m.pdf",
        file_type="pdf",
        file_size=100,
        is_default=True,
    )
    db.add(resume)
    db.commit()
    assert master_skills_ready(db, user.id, resume)
    assert persist_master_skills_from_profile(db, user.id, resume)
    db.refresh(resume)
    assert resume.master_skills == ["Python", "SQL"]


def test_validate_rejects_unknown_master():
    problems = validate_tailor_patch(
        ["Python"],
        "Python job",
        "Python developer",
        {"subskills_display": [{"master": "Java", "items": ["Spring"]}]},
    )
    assert any("unknown master" in p.lower() for p in problems)
