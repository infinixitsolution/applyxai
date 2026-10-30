"""Custom application questions (employer-specific screening rules)."""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import User
from backend.app.services import custom_questions_service

router = APIRouter(tags=["questions"])


@router.get("/questions", summary="Custom application questions")
def list_questions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(custom_questions_service.list_custom_questions(db, user))


@router.post(
    "/questions/sync-from-profile",
    summary="Fill custom question answers from the default resume with AI",
)
def sync_questions_from_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("10/hour", "questions-sync-from-profile", str(user.id))
    return ok(custom_questions_service.sync_custom_questions_from_profile(db, user))


@router.put("/questions", summary="Replace all custom application questions")
def replace_questions(body: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = body.get("items") if isinstance(body, dict) else None
    if not isinstance(items, list):
        raise AppError("VALIDATION_ERROR", "items must be a list", 422)
    try:
        return ok(custom_questions_service.replace_custom_questions(db, user, items))
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None


@router.patch("/questions/{question_id}", summary="Update one custom question")
def patch_question(
    question_id: str,
    body: dict = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ok(custom_questions_service.update_custom_question(db, user, question_id, body))
    except LookupError:
        raise AppError("NOT_FOUND", "Question not found", 404) from None
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None


@router.delete("/questions/{question_id}", summary="Delete a custom question")
def delete_question(question_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        custom_questions_service.delete_custom_question(db, user, question_id)
    except LookupError:
        raise AppError("NOT_FOUND", "Question not found", 404) from None
    return ok({"deleted": True})
