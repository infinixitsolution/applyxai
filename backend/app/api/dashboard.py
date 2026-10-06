from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.models import User
from backend.app.schemas.activity import ApplicationOut
from backend.app.services import dashboard_service, usage_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats", summary="Counts, 30-day chart data, recent applications, automation and usage")
def dashboard_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = dashboard_service.stats(db, user.id)
    data["recent_applications"] = [ApplicationOut.model_validate(a).model_dump(mode="json")
                                   for a in data["recent_applications"]]
    return ok(data)


@router.get("/usage", summary="This month's usage against your plan limits")
def usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(usage_service.usage_summary(db, user.id))
