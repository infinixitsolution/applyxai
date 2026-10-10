"""Optional Windows Credential Manager storage for the device token (see docs/BACKLOG.md #21)."""

from __future__ import annotations

import logging

logger = logging.getLogger("applyxai.agent.credentials")

_SERVICE = "ApplyXAI"
_USER = "agent_device_token"


def store_token(token: str) -> bool:
    if not token:
        return False
    try:
        import keyring

        keyring.set_password(_SERVICE, _USER, token)
        return True
    except Exception as exc:
        logger.debug("Credential Manager unavailable (%s)", exc)
        return False


def load_token() -> str | None:
    try:
        import keyring

        value = keyring.get_password(_SERVICE, _USER)
        return value if value else None
    except Exception:
        return None


def clear_token() -> None:
    try:
        import keyring

        keyring.delete_password(_SERVICE, _USER)
    except Exception:
        pass
