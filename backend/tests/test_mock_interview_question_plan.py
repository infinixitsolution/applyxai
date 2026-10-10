"""JD ↔ resume question plan for mock interviews."""

from backend.app.services.mock_interview_question_plan import (
    build_question_plan,
    extract_jd_bullets,
    jd_resume_overlap,
    resume_profile_block,
)


def test_extract_jd_bullets_from_list():
    jd = """
    About the role
    - Build REST APIs in Python and FastAPI
    - Lead migration to AWS
    """
    bullets = extract_jd_bullets(jd)
    assert any("FastAPI" in b for b in bullets)


def test_overlap_prefers_shared_skills():
    overlap, gaps, extra = jd_resume_overlap(
        ["Python", "FastAPI", "Kubernetes"],
        ["Python", "Django", "PostgreSQL"],
    )
    assert "python" in overlap
    assert "kubernetes" in gaps
    assert "django" in extra


def test_build_question_plan_includes_companies_and_jd():
    intake = {
        "work_history": [
            {"title": "Backend Engineer", "company": "Acme Corp", "summary": "Built payment APIs with Python."},
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "summary": "Backend developer",
    }
    plan = build_question_plan(
        job_title="Senior Python Engineer",
        company="Hired Co",
        job_description="- 5+ years Python\n- Experience with FastAPI and cloud deployments",
        resume_intake=intake,
    )
    assert "QUESTION PLAN" in plan
    assert "Acme Corp" in plan
    assert "FastAPI" in plan
    assert "Overlap" in plan
    assert "Do not drift" in plan or "Do not ask about frameworks" in plan


def test_resume_profile_block_parses_work():
    block = resume_profile_block(
        {
            "work_history": [{"title": "Dev", "company": "X", "summary": "Led React migration"}],
            "skills": ["React"],
        }
    )
    assert block["companies"] == ["X"]
    assert "Dev" in block["roles"][0]
