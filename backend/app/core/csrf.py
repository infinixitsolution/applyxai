"""
Double-submit CSRF protection.

Cookies carry authority, so any state-changing request that arrives WITH an auth cookie
must also echo the CSRF cookie in the X-CSRF-Token header. A cross-site page can make the
browser send cookies but can't read them, so it can't produce the header. Requests with no
auth cookie have no ambient authority and are left alone, as are the pre-login endpoints.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from backend.app.core.errors import error_response

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EXEMPT_PATHS = {
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/verify-email",
    "/api/auth/resend-verification",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        cookies = request.cookies
        if ACCESS_COOKIE not in cookies and REFRESH_COOKIE not in cookies:
            return await call_next(request)
        expected = cookies.get(CSRF_COOKIE, "")
        provided = request.headers.get(CSRF_HEADER, "")
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            return error_response(403, "CSRF_FAILED", "Missing or invalid CSRF token. Refresh the page and try again.")
        return await call_next(request)
