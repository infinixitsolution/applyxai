import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import Notification, User, UserProfile
from backend.app.services import platform_settings_service as ps
from backend.app.services import template_service as ts
from backend.app.services.email_service import get_email_sender, notification_email, smtp_configured


def _user_email_enabled(db: Session, user_id: uuid.UUID, event_type: str) -> bool:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is None:
        return True
    prefs = profile.notification_email or {}
    return bool(prefs.get(event_type, True))


def notify_event(
    db: Session,
    user_id: uuid.UUID,
    type: str,
    *,
    link: str = "",
    variables: dict[str, str] | None = None,
    title: str | None = None,
    body: str | None = None,
) -> Notification:
    """Create in-app notification; optional email from templates and platform/user prefs."""
    if link and (not link.startswith("/") or link.startswith("//") or "\\" in link):
        raise ValueError("notification links must be in-app paths like /automation")
    vars_merged = {k: str(v) for k, v in (variables or {}).items()}
    auth = ps.get_effective_auth(db)
    if link:
        vars_merged.setdefault("link_url", f"{auth.frontend_url}{link}")
    else:
        vars_merged.setdefault("link_url", auth.frontend_url)

    resolved_title = title
    resolved_body = body or ""
    if resolved_title is None:
        resolved_title = ts.event_copy(db, type, "in_app_title", **vars_merged) or vars_merged.get("title", "")
    if body is None:
        resolved_body = ts.event_copy(db, type, "in_app_body", **vars_merged) or vars_merged.get("body", "")
    if not resolved_title:
        resolved_title = type.replace("_", " ").title()

    note = Notification(
        user_id=user_id,
        type=type[:50],
        title=resolved_title[:255],
        body=resolved_body[:5000],
        link=link[:512],
    )
    db.add(note)
    db.flush()

    if ps.notification_email_enabled(db, type) and smtp_configured(db) and _user_email_enabled(db, user_id, type):
        user = db.get(User, user_id)
        if user and user.is_verified and user.is_active:
            email_vars = {**vars_merged, "title": resolved_title, "body": resolved_body}
            subj = ts.event_copy(db, type, "email_subject", **email_vars) or f"{auth.app_name}: {resolved_title}"
            email_body = ts.event_copy(db, type, "email_body", **email_vars)
            email_html = ts.event_copy(db, type, "email_html", **email_vars)
            if not email_body:
                email_body = f"{resolved_title}\n\n{resolved_body}".strip()
            try:
                get_email_sender(db).send(
                    notification_email(user.email, subj, email_body, link, db, html=email_html)
                )
            except Exception:
                pass
    return note


def notify(db: Session, user_id: uuid.UUID, type: str, title: str, body: str = "", link: str = "") -> Notification:
    """Backward-compatible: explicit title/body override template in-app copy."""
    return notify_event(db, user_id, type, link=link, title=title, body=body)


def list_query(user_id: uuid.UUID, unread_only: bool = False):
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return stmt.order_by(Notification.created_at.desc(), Notification.id)


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    note = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if note is None:
        raise AppError("NOT_FOUND", "Notification not found", status_code=404)
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        db.commit()
    return note


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount
