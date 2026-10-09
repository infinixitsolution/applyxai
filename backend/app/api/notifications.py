import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.pagination import PageParams, page_params, page_response, paginate
from backend.app.models import User
from backend.app.schemas.activity import NotificationOut, NotificationPreferencesIn
from backend.app.services import notification_service, preferences_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(note) -> dict:
    return NotificationOut.model_validate(note).model_dump(mode="json")


@router.get("", summary="Your notifications, newest first")
def list_notifications(unread_only: bool = False, page: PageParams = Depends(page_params),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = paginate(db, notification_service.list_query(user.id, unread_only), page)
    data = page_response([_out(n) for n in items], total, page)
    data["unread_count"] = notification_service.unread_count(db, user.id)
    return ok(data)


@router.post("/read-all", summary="Mark all notifications as read")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"marked": notification_service.mark_all_read(db, user.id)})


@router.post("/{notification_id}/read", summary="Mark one notification as read")
def read_one(notification_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_out(notification_service.mark_read(db, user.id, notification_id)))
