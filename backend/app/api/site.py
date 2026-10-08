"""Public site content (CMS). No authentication."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.services import platform_settings_service as ps

router = APIRouter(prefix="/site", tags=["site"])


@router.get("/public", summary="Public branding, banner, landing copy, and legal text")
def public_site(db: Session = Depends(get_db)):
    return ok(ps.get_public_site(db))
