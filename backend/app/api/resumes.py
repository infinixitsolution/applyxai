import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import User
from backend.app.schemas.profile import ResumeOut, ResumeRenameIn
from backend.app.schemas.resume_ai import (
    MasterSkillsUpdateIn,
    ResumeAiPreviewIn,
    ResumeAiTailorIn,
    ResumeApplyStyleIn,
    ResumeIntakeIn,
)
from backend.app.services import resume_ai_service, resume_service
from backend.app.services.resume_templates import list_templates
from backend.app.services.ai_service import ai_available
from backend.app.services.usage_service import plan_limits

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _out(resume) -> dict:
    return ResumeOut.model_validate(resume).model_dump(mode="json")


@router.get("", summary="List your resumes")
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"resumes": [_out(r) for r in resume_service.list_resumes(db, user)],
               "limit": plan_limits(db, user.id)["resumes"]})


@router.get("/templates", summary="List resume style templates")
def resume_templates():
    return ok({"templates": list_templates()})


@router.post("", status_code=201, summary="Upload a PDF or DOCX resume")
async def upload_resume(file: UploadFile = File(...), name: str | None = Form(default=None, max_length=255),
                        user: User = Depends(get_current_user), db: Session = Depends(get_db),
                        limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "resume-upload", str(user.id))
    return ok(_out(await resume_service.upload_resume(db, user, file, name)))


@router.patch("/{resume_id}", summary="Rename a resume")
def rename_resume(resume_id: uuid.UUID, body: ResumeRenameIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return ok(_out(resume_service.rename_resume(db, user, resume_id, body.name)))


@router.post("/{resume_id}/default", summary="Make this your default resume")
def make_default(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_out(resume_service.set_default(db, user, resume_id)))


@router.delete("/{resume_id}", summary="Delete a resume")
def delete_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume_service.delete_resume(db, user, resume_id)
    return ok({"deleted": True})


@router.post("/{resume_id}/analyze-master", summary="Parse resume and suggest master skills")
def analyze_master(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_out(resume_ai_service.analyze_master(db, user, resume_id)))


@router.post("/{resume_id}/intake", summary="Extract profile, cover letter, and skills from a resume")
def resume_intake(
    resume_id: uuid.UUID,
    body: ResumeIntakeIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("30/hour", "resume-intake", str(user.id))
    payload = body or ResumeIntakeIn()
    return ok(resume_ai_service.intake_from_resume(db, user, resume_id, apply=payload.apply))


@router.patch("/{resume_id}/master-skills", summary="Confirm master skills (immutable during tailor)")
def update_master_skills(resume_id: uuid.UUID, body: MasterSkillsUpdateIn, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    resume = resume_service.get_resume(db, user, resume_id)
    cleaned = [s.strip() for s in body.master_skills if s.strip()]
    if not cleaned:
        raise AppError("VALIDATION", "At least one master skill is required.", 422)
    resume.master_skills = cleaned[:80]
    db.commit()
    db.refresh(resume)
    return ok(_out(resume))


@router.post("/ai/preview", summary="Preview JD match and tailor (no save)")
def ai_preview(body: ResumeAiPreviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not ai_available(db, feature="resume"):
        raise AppError("AI_DISABLED", "Platform AI is not enabled for resume features.", 503)
    return ok(resume_ai_service.preview(db, user, resume_id=body.resume_id, job_description=body.job_description))


@router.post("/ai/tailor", status_code=201, summary="Tailor resume to JD and save as new upload")
async def ai_tailor(body: ResumeAiTailorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
                    limiter: RateLimiter = Depends(get_rate_limiter)):
    if not ai_available(db, feature="resume"):
        raise AppError("AI_DISABLED", "Platform AI is not enabled for resume features.", 503)
    limiter.hit("20/hour", "resume-ai-tailor", str(user.id))
    resume = await resume_ai_service.tailor_and_save(
        db,
        user,
        resume_id=body.resume_id,
        job_description=body.job_description,
        job_id=body.job_id,
        template_id=body.template_id,
        application_id=body.application_id,
    )
    return ok(_out(resume))


@router.post("/{resume_id}/apply-style", status_code=201, summary="Save a styled DOCX copy using a template")
async def apply_resume_style(
    resume_id: uuid.UUID,
    body: ResumeApplyStyleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("30/hour", "resume-style", str(user.id))
    return ok(
        _out(
            await resume_service.apply_style_and_save(
                db, user, resume_id, body.template_id, application_id=body.application_id,
            )
        )
    )


@router.get("/{resume_id}/download", summary="Download a resume")
def download_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = resume_service.get_resume(db, user, resume_id)
    path = resume_service.absolute_path(resume)
    if not path.is_file():
        raise AppError("NOT_FOUND", "Resume file is missing", status_code=404)
    return FileResponse(
        path, media_type=resume_service.MIME_BY_TYPE[resume.file_type], filename=resume.filename,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
