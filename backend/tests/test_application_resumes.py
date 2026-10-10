import pytest

from backend.app.core.security import hash_password
from backend.app.models import ApplicationStatus, Job, Resume, User
from backend.app.services import application_service


@pytest.fixture
def users(db):
    alice = User(email="alice-resume@example.com", password_hash=hash_password("x" * 12), is_verified=True)
    db.add(alice)
    db.commit()
    return alice


def test_attach_generated_resume_links_application(db, users):
    alice = users
    job = Job(platform="linkedin", external_id="12345", title="Engineer", company="Acme", job_url="https://example.com/j/1")
    db.add(job)
    db.flush()
    app = application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED)
    resume = Resume(
        user_id=alice.id,
        name="Tailored v1",
        filename="v1.docx",
        storage_path="resumes/a/v1.docx",
        file_type="docx",
        file_size=10,
    )
    db.add(resume)
    db.flush()
    application_service.attach_generated_resume(db, alice.id, app.id, resume.id)
    db.commit()
    db.refresh(app)
    db.refresh(resume)
    assert resume.application_id == app.id
    assert app.resume_id == resume.id


def test_generated_resumes_grouped(db, users):
    alice = users
    job = Job(platform="linkedin", external_id="999", title="Dev", company="Co", job_url="https://example.com/j/2")
    db.add(job)
    db.flush()
    app = application_service.record_application(db, alice.id, job, ApplicationStatus.APPLIED)
    r1 = Resume(user_id=alice.id, name="v1", filename="v1.docx", storage_path="resumes/a/1.docx", file_type="docx", file_size=1)
    r2 = Resume(user_id=alice.id, name="v2", filename="v2.docx", storage_path="resumes/a/2.docx", file_type="docx", file_size=1)
    r1.application_id = app.id
    r2.application_id = app.id
    db.add_all([r1, r2])
    db.commit()
    grouped = application_service.generated_resumes_for_applications(db, alice.id, [app.id])
    assert len(grouped[app.id]) == 2


def test_resumes_by_external_job_finds_the_tailored_copy(db, users):
    alice = users
    resume = Resume(
        user_id=alice.id,
        name="Ada_Backend_Acme_5 years",
        filename="Ada_Backend_Acme_5 years.docx",
        storage_path="resumes/a/tailored.docx",
        file_type="docx",
        file_size=10,
        ai_metadata={"generated_by": "ai", "job_id": "4392", "job_title": "Backend Engineer", "company": "Acme"},
    )
    other = Resume(
        user_id=alice.id,
        name="Master",
        filename="master.docx",
        storage_path="resumes/a/master.docx",
        file_type="docx",
        file_size=10,
        ai_metadata={"generated_by": "ai", "job_id": "other"},
    )
    db.add_all([resume, other])
    db.commit()
    found = application_service.resumes_by_external_job(db, alice.id, ["4392"])
    assert [row.id for row in found["4392"]] == [resume.id]
