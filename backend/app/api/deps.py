"""Request dependencies: the authenticated user or agent device, admin guard, and client identity."""

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.core.cookies import ACCESS_COOKIE
from backend.app.core.database import get_db
from backend.app.core.errors import AppError
from backend.app.core.security import decode_access_token
from backend.app.models import AgentDevice, User
from backend.app.services import agent_service


def _unauthorized() -> AppError:
    return AppError("UNAUTHORIZED", "Please log in to continue.", 401)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    claims = decode_access_token(request.cookies.get(ACCESS_COOKIE, ""))
    if claims is None:
        raise _unauthorized()
    try:
        user = db.get(User, uuid.UUID(claims["sub"]))
    except ValueError:
        raise _unauthorized()
    if user is None or not user.is_active or claims["ver"] != user.token_version:
        raise _unauthorized()
    return user


def get_current_device(request: Request, db: Session = Depends(get_db)) -> AgentDevice:
    """The desktop agent calling with `Authorization: Bearer <device token>`. Never reads cookies."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    device = agent_service.authenticate(db, token.strip()) if scheme.lower() == "bearer" else None
    if device is None:
        raise AppError("DEVICE_UNAUTHORIZED",
                       "This computer isn't connected to ApplyXAI. Run `python -m agent pair` to connect it.", 401)
    return device


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise AppError("FORBIDDEN", "You don't have permission to do that.", 403)
    return user


def client_ip(request: Request) -> str:
    # Behind Nginx, run uvicorn with --proxy-headers so this is the real client address.
    return request.client.host if request.client else "unknown"
