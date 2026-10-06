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
from backend.app.services import resume_service
from backend.app.services.usage_service import plan_limits

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _out(resume) -> dict:
    return ResumeOut.model_validate(resume).model_dump(mode="json")


@router.get("", summary="List your resumes")
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"resumes": [_out(r) for r in resume_service.list_resumes(db, user)],
               "limit": plan_limits(db, user.id)["resumes"]})


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
