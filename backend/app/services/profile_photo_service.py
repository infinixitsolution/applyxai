"""Profile photo upload and removal."""

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from backend.app.models import User, UserProfile

_MAX_BYTES = 2 * 1024 * 1024
_ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
_MIME_BY_EXT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}


def _root() -> Path:
    return Path(get_settings().STORAGE_DIR).resolve()


def _ensure_profile(db: Session, user: User) -> UserProfile:
    if user.profile is None:
        user.profile = UserProfile(user_id=user.id)
        db.add(user.profile)
        db.flush()
    return user.profile


def photo_path(profile: UserProfile) -> Path | None:
    key = (profile.photo_storage_key or "").strip()
    if not key:
        return None
    root = _root()
    path = (root / key).resolve()
    if root not in path.parents and path != root:
        return None
    return path if path.is_file() else None


async def upload_photo(db: Session, user: User, upload: UploadFile) -> UserProfile:
    profile = _ensure_profile(db, user)
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED.get(declared)
    if ext is None:
        name = (upload.filename or "").lower()
        for candidate, mime in _MIME_BY_EXT.items():
            if name.endswith(f".{candidate}"):
                ext = candidate if candidate != "jpeg" else "jpg"
                declared = mime
                break
    if ext is None:
        raise AppError("VALIDATION_ERROR", "Photo must be JPEG, PNG, WebP, or GIF", 422)

    data = await upload.read()
    if len(data) > _MAX_BYTES:
        raise AppError("FILE_TOO_LARGE", "Photos must be 2 MB or smaller", 413)
    if not data:
        raise AppError("VALIDATION_ERROR", "Empty file", 422)

    rel = Path("profile_photos") / f"{user.id}.{ext}"
    abs_path = (_root() / rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)
    profile.photo_storage_key = rel.as_posix()
    db.commit()
    db.refresh(profile)
    return profile


def delete_photo(db: Session, user: User) -> None:
    profile = _ensure_profile(db, user)
    path = photo_path(profile)
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    profile.photo_storage_key = ""
    db.commit()
