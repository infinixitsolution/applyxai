"""Campus partnership banner used in outreach email and WhatsApp sends."""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from backend.app.core.config import PROJECT_ROOT
from backend.app.core.errors import AppError
from backend.app.services.institute_proposal_service import proposal_image_public_url

_IMAGE_NAME = "campus-partnership-proposal.jpg"
_MAX_BYTES = 8 * 1024 * 1024
_ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}


def _destinations() -> list[Path]:
    return [
        PROJECT_ROOT / "assets" / "outreach" / _IMAGE_NAME,
        PROJECT_ROOT / "frontend" / "public" / "outreach" / _IMAGE_NAME,
    ]


def proposal_image_info() -> dict:
    paths = _destinations()
    existing = next((p for p in paths if p.is_file()), None)
    updated_at = None
    if existing is not None:
        updated_at = existing.stat().st_mtime
    return {
        "url": proposal_image_public_url(),
        "exists": existing is not None,
        "updated_at": updated_at,
    }


async def save_proposal_image(upload: UploadFile) -> dict:
    name = (upload.filename or "").lower()
    suffix = Path(name).suffix
    if suffix not in _ALLOWED:
        raise AppError(
            "VALIDATION_ERROR",
            "Upload a JPG, PNG, or WebP image for the partnership banner.",
            422,
        )
    data = await upload.read()
    if not data:
        raise AppError("VALIDATION_ERROR", "Empty image file.", 422)
    if len(data) > _MAX_BYTES:
        raise AppError("VALIDATION_ERROR", "Image is too large (max 8 MB).", 422)
    written: list[str] = []
    for dest in _destinations():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(str(dest))
    return {"url": proposal_image_public_url(), "paths": written}
