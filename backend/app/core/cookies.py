"""Session cookies. Auth cookies are HttpOnly; the CSRF cookie is readable by the SPA on purpose."""

import secrets

from fastapi import Response

from backend.app.core.config import settings

ACCESS_COOKIE = "applyxai_access"
REFRESH_COOKIE = "applyxai_refresh"
CSRF_COOKIE = "applyxai_csrf"
CSRF_HEADER = "X-CSRF-Token"

# The refresh token is only ever sent to the auth endpoints that need it.
_REFRESH_PATH = "/api/auth"


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {"secure": settings.cookie_secure, "samesite": "lax"}
    refresh_age = settings.REFRESH_TOKEN_DAYS * 86400
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=settings.ACCESS_TOKEN_MINUTES * 60,
                        httponly=True, path="/api", **common)
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=refresh_age,
                        httponly=True, path=_REFRESH_PATH, **common)
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(32), max_age=refresh_age,
                        httponly=False, path="/", **common)


def clear_session_cookies(response: Response) -> None:
    common = {"secure": settings.cookie_secure, "samesite": "lax"}
    response.delete_cookie(ACCESS_COOKIE, path="/api", httponly=True, **common)
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH, httponly=True, **common)
    response.delete_cookie(CSRF_COOKIE, path="/", **common)
