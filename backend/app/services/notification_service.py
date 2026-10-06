import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import Notification


def notify(db: Session, user_id: uuid.UUID, type: str, title: str, body: str = "", link: str = "") -> Notification:
    """Server-side only. `link` must be an in-app path, so notifications can't become open redirects."""
    if link and (not link.startswith("/") or link.startswith("//") or "\\" in link):
        raise ValueError("notification links must be in-app paths like /automation")
    note = Notification(user_id=user_id, type=type[:50], title=title[:255], body=body[:5000], link=link[:512])
    db.add(note)
    db.flush()
    return note


def list_query(user_id: uuid.UUID, unread_only: bool = False):
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return stmt.order_by(Notification.created_at.desc(), Notification.id)


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Notification)
                     .where(Notification.user_id == user_id, Notification.read_at.is_(None)))


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    note = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if note is None:
        raise AppError("NOT_FOUND", "Notification not found", status_code=404)
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        db.commit()
    return note


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    result = db.execute(update(Notification)
                        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
                        .values(read_at=datetime.now(timezone.utc)))
    db.commit()
    return result.rowcount
