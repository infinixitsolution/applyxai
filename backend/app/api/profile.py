from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.models import User
from backend.app.schemas.profile import ProfileIn, ProfileOut, SearchConfigIn, SearchConfigOut
from backend.app.services import preferences_service
from backend.app.services.engine_fields import APPLICATION_FIELDS, SEARCH_EXTRA_FIELDS, FieldErrors, describe
from automation import options

router = APIRouter(tags=["profile"])


@router.get("/profile", summary="Your profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProfileOut(**preferences_service.get_profile(db, user)).model_dump(mode="json"))


@router.put("/profile", summary="Replace your profile")
def put_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProfileOut(**preferences_service.update_profile(db, user, body)).model_dump(mode="json"))


@router.get("/preferences/options", summary="Allowed values and form metadata for preferences")
def get_options(user: User = Depends(get_current_user)):
    return ok({
        "search": {
            "experience_level": options.EXPERIENCE_LEVELS,
            "job_type": options.JOB_TYPES,
            "on_site": options.WORK_SETTINGS,
            "date_posted": options.DATE_POSTED,
            "sort_by": options.SORT_BY,
            "extra_fields": describe(SEARCH_EXTRA_FIELDS),
        },
        "application_fields": describe(APPLICATION_FIELDS),
    })


def _search_out(config) -> dict:
    if config is None:
        return {**SearchConfigOut(keywords=[]).model_dump(mode="json"), "configured": False}
    return {**SearchConfigOut.model_validate(config, from_attributes=True).model_dump(mode="json"), "configured": True}


@router.get("/preferences/search", summary="Your job search settings (defaults until first saved)")
def get_search(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_search_out(preferences_service.get_search(db, user)))


@router.put("/preferences/search", summary="Replace your job search settings")
def put_search(body: SearchConfigIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_search_out(preferences_service.update_search(db, user, body)))


@router.get("/preferences/application", summary="Your saved application answers")
def get_application(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(preferences_service.get_application(db, user))


@router.patch("/preferences/application", summary="Update application answers (null resets a key)")
def patch_application(body: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return ok(preferences_service.update_application(db, user, body))
    except FieldErrors as exc:
        raise AppError("VALIDATION_ERROR", "Some settings are invalid", status_code=422, details=exc.errors) from None


@router.post("/preferences/application/resolve-pending", summary="Answer LinkedIn questions collected during automation")
def resolve_pending(body: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, list):
        raise AppError("VALIDATION_ERROR", "answers must be a list", 422)
    try:
        return ok(preferences_service.resolve_pending_questions(db, user, answers))
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None
