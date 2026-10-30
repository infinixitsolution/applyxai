from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.profile_taxonomies import (
    DEPARTMENTS,
    EDUCATION_LEVELS,
    EMPLOYMENT_TYPES,
    INDUSTRIES,
    JOB_ROLES,
    SKILL_CATEGORIES,
)
from backend.app.models import User
from backend.app.schemas.profile import ProfileIn, SearchConfigIn, SearchConfigOut
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.services import (
    career_ai_service,
    common_answers_ai_service,
    employment_ai_service,
    master_profile_service,
    preferences_service,
    professional_ai_service,
    profile_ai_enhance_service,
    profile_photo_service,
    projects_ai_service,
    screening_ai_service,
    skills_ai_service,
)
from backend.app.services.engine_fields import (
    APPLICATION_FIELDS,
    PROFILE_ANSWER_FIELDS,
    RUN_SETTINGS_FIELDS,
    SEARCH_EXTRA_FIELDS,
    FieldErrors,
    describe,
)
from automation import options

router = APIRouter(tags=["profile"])


@router.get("/profile", summary="Master profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(master_profile_service.master_profile_payload(db, user))


@router.put("/profile", summary="Replace core profile fields")
def put_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preferences_service.update_profile(db, user, body)
    db.refresh(user)
    return ok(master_profile_service.master_profile_payload(db, user))


@router.patch("/profile/sections/{section}", summary="Update one master profile section")
def patch_profile_section(
    section: str,
    body: dict = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = body.get("data") if isinstance(body, dict) and "data" in body else body
    try:
        master_profile_service.update_master_section(db, user, section, payload)
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None
    db.refresh(user)
    return ok(master_profile_service.master_profile_payload(db, user))


@router.post(
    "/profile/ai-enhance",
    summary="Fill Master Profile sections from the default resume in one pass",
)
def enhance_master_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("10/hour", "profile-ai-enhance", str(user.id))
    return ok(profile_ai_enhance_service.enhance_master_profile(db, user))


@router.post("/profile/sections/career/ai-enhance", summary="Expand preferred roles and locations from the profile")
def enhance_career(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "career-ai-enhance", str(user.id))
    return ok(career_ai_service.enhance_career_preferences(db, user))


@router.post(
    "/profile/sections/professional/ai-complete",
    summary="Complete professional headline and summary from the resume",
)
def complete_professional(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "professional-ai-complete", str(user.id))
    return ok(professional_ai_service.complete_professional_overview(db, user))


@router.post(
    "/profile/sections/common_answers/ai-fill",
    summary="Fill empty common application answers from the resume and profile",
)
def fill_common_answers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "common-answers-ai-fill", str(user.id))
    return ok(common_answers_ai_service.fill_common_answers_from_resume(db, user))


@router.post(
    "/profile/sections/screening/ai-fill",
    summary="Fill empty engine screening answers from the resume and profile",
)
def fill_screening_answers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "screening-ai-fill", str(user.id))
    return ok(screening_ai_service.fill_screening_from_resume(db, user))


@router.post(
    "/profile/sections/employment/ai-fill",
    summary="Fill jobs from the resume, or mark Fresher when there is no employer",
)
def fill_employment(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "employment-ai-fill", str(user.id))
    return ok(employment_ai_service.fill_employment_from_resume(db, user))


@router.post(
    "/profile/sections/projects/ai-fill",
    summary="Fill projects from the resume (academic for freshers, work projects when employed)",
)
def fill_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "projects-ai-fill", str(user.id))
    return ok(projects_ai_service.fill_projects_from_resume(db, user))


@router.post(
    "/profile/sections/skills/ai-fill",
    summary="Fill IT skills from the default resume without inventing tools",
)
def fill_skills(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.hit("20/hour", "skills-ai-fill", str(user.id))
    return ok(skills_ai_service.fill_skills_from_resume(db, user))


@router.get("/profile/taxonomies", summary="Industry and career taxonomy options")
def profile_taxonomies(user: User = Depends(get_current_user)):
    return ok({
        "industries": INDUSTRIES,
        "departments": DEPARTMENTS,
        "job_roles": JOB_ROLES,
        "education_levels": EDUCATION_LEVELS,
        "employment_types": EMPLOYMENT_TYPES,
        "skill_categories": SKILL_CATEGORIES,
    })


@router.post("/profile/photo", summary="Upload or replace profile photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    await profile_photo_service.upload_photo(db, user, file)
    db.refresh(user)
    return ok(master_profile_service.master_profile_payload(db, user))


@router.get("/profile/photo", summary="Download profile photo")
def get_profile_photo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.profile is None:
        raise AppError("NOT_FOUND", "No profile photo", 404)
    path = profile_photo_service.photo_path(user.profile)
    if path is None:
        raise AppError("NOT_FOUND", "No profile photo", 404)
    return FileResponse(path, media_type="image/jpeg", filename=path.name)


@router.delete("/profile/photo", summary="Remove profile photo")
def delete_profile_photo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile_photo_service.delete_photo(db, user)
    db.refresh(user)
    return ok(master_profile_service.master_profile_payload(db, user))


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
        "profile_answer_fields": describe(PROFILE_ANSWER_FIELDS),
        "run_settings_fields": describe(RUN_SETTINGS_FIELDS),
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


def _suggest_pending_ai(body: dict, user: User, db: Session):
    ids = body.get("ids") if isinstance(body, dict) else None
    if ids is not None and not isinstance(ids, list):
        raise AppError("VALIDATION_ERROR", "ids must be a list when provided", 422)
    try:
        return ok(preferences_service.suggest_pending_ai_answers(db, user, ids=ids))
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None


@router.post("/preferences/application/resolve-pending", summary="Answer LinkedIn questions collected during automation")
def resolve_pending(body: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if isinstance(body, dict) and body.get("mode") == "ai_suggest":
        return _suggest_pending_ai(body, user, db)
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, list):
        raise AppError("VALIDATION_ERROR", "answers must be a list", 422)
    try:
        return ok(preferences_service.resolve_pending_questions(db, user, answers))
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422) from None


@router.post(
    "/preferences/application/suggest-pending-ai",
    summary="Draft answers for pending LinkedIn questions using profile and default resume",
)
def suggest_pending_ai(body: dict = Body(default={}), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _suggest_pending_ai(body if isinstance(body, dict) else {}, user, db)
