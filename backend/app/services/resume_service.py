"""
Resume storage. Files live at STORAGE_DIR/resumes/<user_id>/<uuid>.<ext>; the uploaded name
is kept for display only and never touches the filesystem path.
"""

import hashlib
import io
import logging
import os
import re
import unicodedata
import uuid
import zipfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from backend.app.models import Resume, User
from backend.app.services.usage_service import plan_limits

log = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_BY_TYPE = {"pdf": PDF_MIME, "docx": DOCX_MIME}
# Browsers/OSes sometimes send a generic type; anything else contradicting the extension is rejected.
_GENERIC_MIME = {"", "application/octet-stream", "binary/octet-stream"}
_CHUNK = 64 * 1024


def _invalid(message: str) -> AppError:
    return AppError("INVALID_FILE", message, status_code=422)


def safe_display_name(filename: str | None) -> str:
    name = re.split(r"[\\/]", filename or "")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip(" .")
    name = re.sub(r"\s+", " ", name)
    return name[-255:] or "resume"


def _extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower().lstrip(".")


def _looks_like_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def _looks_like_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
    except (zipfile.BadZipFile, ValueError):
        return False
    # vbaProject.bin means macros (a .docm renamed to .docx).
    return "[Content_Types].xml" in names and "word/document.xml" in names and "word/vbaProject.bin" not in names


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    buf = bytearray()
    while chunk := await upload.read(_CHUNK):
        buf += chunk
        if len(buf) > limit:
            raise AppError("FILE_TOO_LARGE", f"Resumes must be {limit // (1024 * 1024)} MB or smaller", status_code=413)
    return bytes(buf)


def _storage_root() -> Path:
    return Path(get_settings().STORAGE_DIR).resolve()


def absolute_path(resume: Resume) -> Path:
    root = _storage_root()
    path = (root / resume.storage_path).resolve()
    if root not in path.parents:
        raise AppError("NOT_FOUND", "Resume not found", status_code=404)
    return path


def list_resumes(db: Session, user: User) -> list[Resume]:
    return list(db.scalars(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.is_default.desc(), Resume.created_at.desc())
    ))


def get_resume(db: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id))
    if resume is None:
        raise AppError("NOT_FOUND", "Resume not found", status_code=404)
    return resume


async def upload_resume(db: Session, user: User, upload: UploadFile, name: str | None = None) -> Resume:
    limit = plan_limits(db, user.id)["resumes"]
    count = db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user.id))
    if count >= limit:
        raise AppError("PLAN_LIMIT_REACHED",
                       f"Your plan allows {limit} resume{'s' if limit != 1 else ''}. Delete one or upgrade.",
                       status_code=403)

    display = safe_display_name(upload.filename)
    file_type = _extension(display)
    if file_type not in MIME_BY_TYPE:
        raise _invalid("Only PDF and DOCX resumes are supported")
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    if declared not in _GENERIC_MIME and declared != MIME_BY_TYPE[file_type]:
        raise _invalid("The file type does not match its extension")

    data = await _read_limited(upload, get_settings().MAX_RESUME_BYTES)
    if not data:
        raise _invalid("The file is empty")
    if not (_looks_like_pdf(data) if file_type == "pdf" else _looks_like_docx(data)):
        raise _invalid(f"The file is not a valid {file_type.upper()} document")

    rel = f"resumes/{user.id}/{uuid.uuid4().hex}.{file_type}"
    path = _storage_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    label = (name or "").strip()[:255] or os.path.splitext(display)[0][:255] or "Resume"
    resume = Resume(user_id=user.id, name=label, filename=display, storage_path=rel, file_type=file_type,
                    file_size=len(data), sha256=hashlib.sha256(data).hexdigest(), is_default=count == 0)
    db.add(resume)
    try:
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(resume)
    return resume


def rename_resume(db: Session, user: User, resume_id: uuid.UUID, name: str) -> Resume:
    resume = get_resume(db, user, resume_id)
    resume.name = name
    db.commit()
    db.refresh(resume)
    return resume


def set_default(db: Session, user: User, resume_id: uuid.UUID) -> Resume:
    resume = get_resume(db, user, resume_id)
    if not resume.is_default:
        # Clear first: the partial unique index allows only one default per user.
        db.execute(update(Resume).where(Resume.user_id == user.id, Resume.is_default.is_(True))
                   .values(is_default=False))
        db.flush()
        resume.is_default = True
        db.commit()
    db.refresh(resume)
    return resume


def delete_resume(db: Session, user: User, resume_id: uuid.UUID) -> None:
    resume = get_resume(db, user, resume_id)
    path = absolute_path(resume)
    was_default = resume.is_default
    db.delete(resume)
    db.flush()
    if was_default:
        newest = db.scalar(select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc()))
        if newest is not None:
            newest.is_default = True
    db.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        log.warning("Could not delete resume file for resume %s", resume_id)
