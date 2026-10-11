"""Candidate live-interview reports."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.models import User
from backend.app.schemas.live_interview import LiveInterviewApplicationIn
from backend.app.services import live_interview_service

router = APIRouter(prefix="/live-interviews", tags=["live-interviews"])


@router.get("", summary="Live interviews for this account")
def list_mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"sessions": live_interview_service.list_sessions(db, user.id)})


@router.get("/applications", summary="Auto-applied jobs that can be attached to a report")
def applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"applications": live_interview_service.list_applications(db, user.id)})


@router.get("/{session_id}", summary="One live interview report")
def one(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(live_interview_service.get_session(db, user.id, session_id))


@router.put("/{session_id}/application", summary="Attach an auto-applied job to this interview")
def attach_application(
    session_id: uuid.UUID, body: LiveInterviewApplicationIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    result = live_interview_service.attach_application(db, user, session_id, body.application_id)
    db.commit()
    return ok(result)


@router.post("/{session_id}/regenerate", summary="Score the saved transcript again")
def regenerate(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = live_interview_service.regenerate_report(db, user, session_id)
    db.commit()
    return ok(result)
