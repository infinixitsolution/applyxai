"""Detect a dead Selenium session vs transient WebDriver errors."""

from __future__ import annotations

from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException

_SESSION_LOST_MARKERS = (
    "invalid session id",
    "no such window",
    "target window already closed",
    "not connected to devtools",
    "disconnected: unable to receive message from renderer",
    "disconnected: not connected to devtools",
    "session deleted",
    "browser has closed",
    "chrome not reachable",
)


def session_lost(exc: BaseException) -> bool:
    if isinstance(exc, (NoSuchWindowException, InvalidSessionIdException)):
        return True
    if isinstance(exc, WebDriverException):
        msg = (getattr(exc, "msg", None) or str(exc)).lower()
        return any(marker in msg for marker in _SESSION_LOST_MARKERS)
    return False
