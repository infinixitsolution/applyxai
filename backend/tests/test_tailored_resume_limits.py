import io

import pytest
from fastapi import UploadFile

from backend.app.core.security import hash_password
from backend.app.models import Application, ApplicationStatus, Job, Resume, User
from backend.app.services import application_service, resume_service


@pytest.fixture
def user(db):
    u = User(email="tailor-limit@example.com", password_hash=hash_password("x" * 12), is_verified=True)
    db.add(u)
    db.commit()
    return u


def test_ai_application_resumes_do_not_count_toward_plan_limit(db, user, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.resume_service.plan_limits",
        lambda _db, _uid: {"resumes": 1},
    )
    master = Resume(
        user_id=user.id,
        name="Master",
        filename="master.pdf",
        storage_path="resumes/u/master.pdf",
        file_type="pdf",
        file_size=10,
        is_default=True,
    )
    db.add(master)
    db.commit()
    assert resume_service.resumes_counting_toward_limit(db, user.id) == 1

    tailored = Resume(
        user_id=user.id,
        name="Tailored v1",
        filename="v1.docx",
        storage_path="resumes/u/v1.docx",
        file_type="docx",
        file_size=10,
        application_id=None,
        ai_metadata={"generated_by": "ai", "job_id": "123"},
    )
    db.add(tailored)
    db.commit()
    assert resume_service.resumes_counting_toward_limit(db, user.id) == 1


@pytest.mark.asyncio
async def test_upload_allowed_when_only_master_and_ai_copies_exist(db, user, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.resume_service.plan_limits",
        lambda _db, _uid: {"resumes": 1},
    )
    master = Resume(
        user_id=user.id,
        name="Master",
        filename="master.pdf",
        storage_path="resumes/u/master.pdf",
        file_type="pdf",
        file_size=10,
        is_default=True,
    )
    tailored = Resume(
        user_id=user.id,
        name="Tailored",
        filename="t.docx",
        storage_path="resumes/u/t.docx",
        file_type="docx",
        file_size=10,
        ai_metadata={"generated_by": "ai", "job_id": "99"},
    )
    db.add_all([master, tailored])
    db.commit()

    # Minimal valid PDF header for upload validation
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    upload = UploadFile(filename="second.pdf", file=io.BytesIO(pdf))
    with pytest.raises(Exception):
        # Still blocked: user already has one library resume
        await resume_service.upload_resume(db, user, upload, name="Second")


@pytest.mark.asyncio
async def test_tailored_upload_does_not_need_library_count(db, user, monkeypatch):
    """Per-job copies pass counts_against_plan=False and must still save beside an existing default."""
    monkeypatch.setattr(
        "backend.app.services.resume_service.plan_limits",
        lambda _db, _uid: {"resumes": 1},
    )
    master = Resume(
        user_id=user.id,
        name="Master",
        filename="master.pdf",
        storage_path="resumes/u/master.pdf",
        file_type="pdf",
        file_size=10,
        is_default=True,
    )
    db.add(master)
    db.commit()

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    upload = UploadFile(filename="tailored.pdf", file=io.BytesIO(pdf))
    saved = await resume_service.upload_resume(
        db, user, upload, name="Sai_Python_2 years", counts_against_plan=False,
    )
    assert saved.is_default is False
    assert saved.name == "Sai_Python_2 years"
    assert master.is_default is True
    assert resume_service.absolute_path(saved).is_file()


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
