"""Temporary storage for WhatsApp chat attachments (local bridge reads the file path)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from backend.app.core.config import settings
from backend.app.core.errors import AppError

_MAX_BYTES = 16 * 1024 * 1024
_ALLOWED_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".mp4",
    ".apk",
}


def _safe_filename(name: str) -> str:
    base = Path(name or "attachment").name
    base = re.sub(r"[^\w.\- ()]", "_", base).strip("._")
    return (base or "attachment")[:180]


async def store_outreach_attachment(lead_id: uuid.UUID, upload: UploadFile) -> tuple[Path, str]:
    original = _safe_filename(upload.filename or "attachment")
    suffix = Path(original).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise AppError(
            "VALIDATION_ERROR",
            f"File type not allowed. Supported: {', '.join(sorted(_ALLOWED_SUFFIXES))}",
            422,
        )
    data = await upload.read()
    if not data:
        raise AppError("VALIDATION_ERROR", "Empty file.", 422)
    if len(data) > _MAX_BYTES:
        raise AppError("VALIDATION_ERROR", "File is too large (max 16 MB for WhatsApp).", 422)
    folder = settings.STORAGE_DIR / "outreach_attachments" / str(lead_id)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{uuid.uuid4().hex}_{original}"
    dest.write_bytes(data)
    return dest, original
