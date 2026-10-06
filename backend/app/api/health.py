import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.errors import error_response, ok

router = APIRouter(tags=["health"])
logger = logging.getLogger("applyxai.api")


@router.get("/health", summary="Liveness and database connectivity")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        return error_response(503, "DATABASE_UNAVAILABLE", "Database is unreachable")
    return ok({"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION})
