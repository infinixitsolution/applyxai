import io

import pytest
from fastapi import UploadFile

from backend.app.core.errors import AppError
from backend.app.core.security import hash_password
from backend.app.models import Application, ApplicationStatus, Job, Resume, User
from backend.app.services import application_service, resume_service, usage_service

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


@pytest.fixture
def user(db):
    u = User(email="tailor-limit@example.com", password_hash=hash_password("x" * 12), is_verified=True)
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def one_resume_a_month(monkeypatch):
    monkeypatch.setattr(usage_service, "plan_limits", lambda _db, _uid: {"resumes": 1})


def test_ai_application_resumes_are_not_library_slots(db, user):
    master = Resume(user_id=user.id, name="Master", filename="master.pdf", storage_path="resumes/u/master.pdf",
                    file_type="pdf", file_size=10, is_default=True)
    db.add(master)
    db.commit()
    assert resume_service.resumes_counting_toward_limit(db, user.id) == 1

    tailored = Resume(user_id=user.id, name="Tailored v1", filename="v1.docx", storage_path="resumes/u/v1.docx",
                      file_type="docx", file_size=10, ai_metadata={"generated_by": "ai", "job_id": "123"})
    db.add(tailored)
    db.commit()
    assert resume_service.resumes_counting_toward_limit(db, user.id) == 1


@pytest.mark.asyncio
async def test_second_upload_in_a_month_is_blocked_on_a_one_resume_plan(db, user, one_resume_a_month):
    await resume_service.upload_resume(db, user, UploadFile(filename="first.pdf", file=io.BytesIO(PDF)))
    assert usage_service.resumes_created(db, user.id) == 1
    with pytest.raises(AppError) as err:
        await resume_service.upload_resume(db, user, UploadFile(filename="second.pdf", file=io.BytesIO(PDF)))
    assert err.value.code == "PLAN_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_auto_apply_copies_skip_the_monthly_limit(db, user, one_resume_a_month):
    """Per-job copies pass counts_against_plan=False: they save past the limit and are not counted."""
    master = await resume_service.upload_resume(db, user, UploadFile(filename="master.pdf", file=io.BytesIO(PDF)))

    saved = await resume_service.upload_resume(
        db, user, UploadFile(filename="tailored.pdf", file=io.BytesIO(PDF)),
        name="Sai_Python_2 years", counts_against_plan=False,
    )
    assert saved.is_default is False
    assert saved.name == "Sai_Python_2 years"
    assert master.is_default is True
    assert resume_service.absolute_path(saved).is_file()
    assert usage_service.resumes_created(db, user.id) == 1


def test_resolve_applied_resume_id_from_ai_metadata(db, user):
    job = Job(platform="linkedin", external_id="555", title="Engineer", company="Co", job_url="https://example.com/j/555")
    db.add(job)
    db.flush()
    app = Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.DISCOVERED)
    tailored = Resume(
        user_id=user.id,
        name="AI copy",
        filename="ai.docx",
        storage_path="resumes/u/ai.docx",
        file_type="docx",
        file_size=10,
        application_id=app.id,
        ai_metadata={"generated_by": "ai", "job_id": "555"},
    )
    db.add_all([app, tailored])
    db.flush()
    application_service.attach_generated_resume(db, user.id, app.id, tailored.id)
    db.commit()

    resolved = application_service.resolve_applied_resume_id(
        db, user.id, job, event_resume_id=None, external_job_id="555",
    )
    assert resolved == tailored.id
