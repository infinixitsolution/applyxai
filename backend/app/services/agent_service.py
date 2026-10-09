"""
Desktop agent devices: pairing, device tokens, and presence.

The Automation page asks for a pairing code (8 characters, 10 minutes, single use). The user
types it into `python -m agent pair` on their computer, and the agent exchanges it for a
device token that only the agent ever sees. Both are high-entropy enough for an unsalted
SHA-256, and only the hashes are stored.
"""

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.core.security import hash_token
from backend.app.models import AgentConnectSession, AgentDevice, User

PAIRING_MINUTES = 10
CONNECT_MINUTES = 15
MAX_DEVICES = 5
ONLINE_SECONDS = 45
TOKEN_PREFIX = "axd_"
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no 0/O or 1/I lookalikes
_CODE_LENGTH = 8


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalize_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def _active_devices(user_id: uuid.UUID):
    return select(AgentDevice).where(AgentDevice.user_id == user_id, AgentDevice.token_hash.is_not(None),
                                     AgentDevice.revoked_at.is_(None))


def create_pairing_code(db: Session, user: User) -> tuple[str, datetime]:
    """A new code for `user`; any earlier unused code stops working. The caller commits."""
    count = db.scalar(select(func.count()).select_from(_active_devices(user.id).subquery()))
    if count >= MAX_DEVICES:
        raise AppError("DEVICE_LIMIT_REACHED",
                       f"You can connect up to {MAX_DEVICES} computers. Remove one to connect another.", 409)
    db.execute(delete(AgentDevice).where(AgentDevice.user_id == user.id, AgentDevice.token_hash.is_(None)))
    code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    expires = _now() + timedelta(minutes=PAIRING_MINUTES)
    db.add(AgentDevice(user_id=user.id, pairing_code_hash=hash_token(code), pairing_expires_at=expires))
    db.flush()
    return f"{code[:4]}-{code[4:]}", expires


def pair(db: Session, code: str, *, name: str, platform: str, agent_version: str) -> tuple[AgentDevice, str]:
    """Exchange a pairing code for a device token (returned once, never stored). The caller commits."""
    device = db.scalar(select(AgentDevice).where(AgentDevice.pairing_code_hash == hash_token(normalize_code(code)),
                                                 AgentDevice.token_hash.is_(None)))
    if device is None or _aware(device.pairing_expires_at) <= _now():
        raise AppError("INVALID_PAIRING_CODE",
                       "That pairing code is wrong or has expired. Get a new one from the Automation page.", 400)
    user = db.get(User, device.user_id)
    if user is None or not user.is_active:
        raise AppError("INVALID_PAIRING_CODE",
                       "That pairing code is wrong or has expired. Get a new one from the Automation page.", 400)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    device.token_hash = hash_token(token)
    device.pairing_code_hash = None
    device.pairing_expires_at = None
    device.name = name.strip()[:100] or "My computer"
    device.platform = platform.strip()[:50]
    device.agent_version = agent_version.strip()[:32]
    device.paired_at = device.last_seen_at = _now()
    db.flush()
    return device, token


def authenticate(db: Session, token: str) -> AgentDevice | None:
    """The paired, unrevoked device for a token whose user is still active."""
    if not token.startswith(TOKEN_PREFIX):
        return None
    device = db.scalar(select(AgentDevice).where(AgentDevice.token_hash == hash_token(token),
                                                 AgentDevice.revoked_at.is_(None)))
    if device is None:
        return None
    user = db.get(User, device.user_id)
    return device if user is not None and user.is_active else None


def touch(device: AgentDevice, *, agent_version: str = "", platform: str = "") -> None:
    device.last_seen_at = _now()
    if agent_version:
        device.agent_version = agent_version[:32]
    if platform:
        device.platform = platform[:50]


def list_devices(db: Session, user_id: uuid.UUID) -> list[AgentDevice]:
    return list(db.scalars(_active_devices(user_id).order_by(AgentDevice.paired_at.desc())))


def revoke(db: Session, user_id: uuid.UUID, device_id: uuid.UUID) -> None:
    device = db.scalar(_active_devices(user_id).where(AgentDevice.id == device_id))
    if device is None:
        raise AppError("NOT_FOUND", "Computer not found", 404)
    device.revoked_at = _now()
    db.flush()


def is_online(device: AgentDevice, now: datetime | None = None) -> bool:
    seen = _aware(device.last_seen_at)
    return seen is not None and (now or _now()) - seen <= timedelta(seconds=ONLINE_SECONDS)


def device_out(device: AgentDevice, now: datetime | None = None) -> dict:
    return {
        "id": str(device.id), "name": device.name, "platform": device.platform,
        "agent_version": device.agent_version,
        "paired_at": device.paired_at.isoformat() if device.paired_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "online": is_online(device, now),
    }


def start_connect_session(
    db: Session,
    *,
    name: str,
    platform: str,
    agent_version: str,
) -> tuple[AgentConnectSession, str]:
    secret = secrets.token_urlsafe(32)
    session = AgentConnectSession(
        secret_hash=hash_token(secret),
        expires_at=_now() + timedelta(minutes=CONNECT_MINUTES),
        requested_name=name.strip()[:100] or "My computer",
        platform=platform.strip()[:50],
        agent_version=agent_version.strip()[:32],
    )
    db.add(session)
    db.flush()
    return session, secret


def approve_connect_session(db: Session, user: User, session_id: uuid.UUID) -> AgentConnectSession:
    session = db.get(AgentConnectSession, session_id)
    if session is None or _aware(session.expires_at) <= _now():
        raise AppError("CONNECT_EXPIRED", "This connection request expired. Open the desktop app and try again.", 400)
    if session.user_id is not None and session.deliver_token:
        return session
    count = db.scalar(select(func.count()).select_from(_active_devices(user.id).subquery()))
    if count >= MAX_DEVICES:
        raise AppError("DEVICE_LIMIT_REACHED",
                       f"You can connect up to {MAX_DEVICES} computers. Remove one to connect another.", 409)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    device = AgentDevice(
        user_id=user.id,
        name=session.requested_name or "My computer",
        platform=session.platform,
        agent_version=session.agent_version,
        token_hash=hash_token(token),
        paired_at=_now(),
        last_seen_at=_now(),
    )
    db.add(device)
    db.flush()
    session.user_id = user.id
    session.device_id = device.id
    session.deliver_token = token
    db.flush()
    return session


def poll_connect_session(db: Session, session_id: uuid.UUID, secret: str) -> dict:
    session = db.get(AgentConnectSession, session_id)
    if session is None or session.secret_hash != hash_token(secret):
        raise AppError("CONNECT_INVALID", "Invalid connection session.", 400)
    if _aware(session.expires_at) <= _now():
        raise AppError("CONNECT_EXPIRED", "This connection request expired.", 400)
    if not session.deliver_token or session.device_id is None:
        return {"status": "pending"}
    token = session.deliver_token
    session.deliver_token = None
    device = db.get(AgentDevice, session.device_id)
    db.flush()
    return {
        "status": "ready",
        "token": token,
        "device_id": str(session.device_id),
        "user_id": str(session.user_id),
        "name": device.name if device else session.requested_name,
    }


def delete_expired_pairings(db: Session, now: datetime | None = None) -> int:
    now = now or _now()
    db.execute(delete(AgentConnectSession).where(AgentConnectSession.expires_at < now))
    return db.execute(delete(AgentDevice).where(AgentDevice.token_hash.is_(None),
                                                AgentDevice.pairing_expires_at < now)).rowcount
