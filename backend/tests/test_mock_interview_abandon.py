"""Stale mock interview session abandonment."""

import uuid
from datetime import datetime, timedelta, timezone

from backend.app.models import MockInterviewSession
from backend.app.models.enums import MockInterviewSessionStatus
from backend.app.services import auth_service, mock_interview_service as svc
from backend.tests.factories import add_application

EMAIL = "abandon-mi@example.com"


def test_mark_stale_sessions_abandoned(db):
    user, _ = auth_service.register(db, EMAIL, "correct horse battery", "Ab", "User")
    assert user is not None
    user.is_verified = True
    db.commit()
    app = add_application(db, EMAIL, "abandon-job", title="Engineer", company="Co", description="Work")
    session = MockInterviewSession(
        id=uuid.uuid4(),
        user_id=user.id,
        application_id=app.id,
        interview_types=["behavioral"],
        status=MockInterviewSessionStatus.ACTIVE,
        turn_count=0,
        context_snapshot={},
    )
    db.add(session)
    db.flush()
    session.updated_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db.commit()

    count = svc.mark_stale_sessions_abandoned(db, idle_hours=24)
    db.commit()

    db.refresh(session)
    assert count >= 1
    assert session.status == MockInterviewSessionStatus.ABANDONED
