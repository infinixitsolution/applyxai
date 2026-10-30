"""LinkedIn profile sync planning and AI completion."""

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.models import User
from backend.app.services import linkedin_profile_ai_service, linkedin_profile_sync_service as lp_sync

router = APIRouter(tags=["profile"])


@router.get("/profile/linkedin/sync-plan", summary="Preview what would sync to LinkedIn")
def sync_plan(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_photo: bool = Query(True),
    dry_run: bool = Query(False),
):
    snapshot = lp_sync.build_snapshot(db, user)
    opts = lp_sync.normalize_start_options({"include_photo": include_photo, "dry_run": dry_run})
    plan = lp_sync.build_sync_plan(
        snapshot,
        sections=opts["sections"],
        overwrite_sections=opts["overwrite_sections"],
        include_photo=opts["include_photo"],
    )
    return ok({"snapshot": snapshot, "plan": plan, "settings": opts})


@router.post("/profile/linkedin/ai-complete", summary="Draft Master Profile text for LinkedIn using AI")
def ai_complete(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(linkedin_profile_ai_service.generate_completion_draft(db, user))


@router.post("/profile/linkedin/apply-ai-draft", summary="Save an approved AI draft to Master Profile")
def apply_ai_draft(body: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    draft = body.get("draft") if isinstance(body, dict) else body
    return ok(linkedin_profile_ai_service.apply_ai_draft(db, user, draft or {}))
