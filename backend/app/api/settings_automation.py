"""Automation runtime settings (browser and submission behavior)."""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.models import User
from backend.app.services import automation_settings_service

router = APIRouter(tags=["settings"])


@router.get("/settings/automation", summary="Automation execution settings")
def get_automation_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(automation_settings_service.get_settings(db, user))


@router.patch("/settings/automation", summary="Update automation execution settings")
def patch_automation_settings(
    body: dict = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not isinstance(body, dict):
        raise AppError("VALIDATION_ERROR", "Expected an object", 422)
    try:
        return ok(automation_settings_service.update_settings(db, user, body))
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None


@router.post("/settings/automation/reset", summary="Reset automation settings to defaults")
def reset_automation_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(automation_settings_service.reset_settings(db, user))
