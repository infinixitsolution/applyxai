from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import client_ip, get_current_user
from backend.app.core.config import settings
from backend.app.core.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, error_response, ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import User
from backend.app.schemas.auth import EmailIn, LoginIn, RegisterIn, ResetPasswordIn, TokenIn, UserOut
from backend.app.services import auth_service
from backend.app.services.email_service import (
    EmailSender, account_exists_email, get_email_sender, password_reset_email, verification_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_CHECK_EMAIL = "If that address can receive email, a message is on its way. Please check your inbox."


def _user(user: User) -> dict:
    return UserOut.model_validate(user).model_dump(mode="json")


@router.post("/register", status_code=202, summary="Create an account and send a verification email")
def register(body: RegisterIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
             limiter: RateLimiter = Depends(get_rate_limiter), mailer: EmailSender = Depends(get_email_sender)):
    limiter.hit("10/hour", "register", client_ip(request))
    user, token = auth_service.register(db, body.email, body.password, body.first_name, body.last_name)
    if user is None:
        background.add_task(mailer.send, account_exists_email(auth_service.normalize_email(body.email)))
    elif token:
        background.add_task(mailer.send, verification_email(user.email, token))
    # Identical answer whether or not the email was already registered.
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        return ok({"message": "You can log in now.", "verification_required": False})
    return ok({"message": _CHECK_EMAIL, "verification_required": True})


@router.post("/login", summary="Log in; sets HttpOnly session cookies")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("5/minute", "login-ip", client_ip(request))
    limiter.hit("10/hour", "login-email", auth_service.normalize_email(body.email))
    session = auth_service.login(db, body.email, body.password)
    set_session_cookies(response, session.access_token, session.refresh_token)
    return ok({"user": _user(session.user)})


@router.post("/refresh", summary="Rotate the session using the refresh cookie")
def refresh(request: Request, response: Response, db: Session = Depends(get_db),
            limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/minute", "refresh", client_ip(request))
    try:
        raw = request.cookies.get(REFRESH_COOKIE)
        if not raw:
            raise auth_service.SESSION_EXPIRED()
        session = auth_service.refresh(db, raw)
    except AppError as exc:
        failed = error_response(exc.status_code, exc.code, exc.message)
        clear_session_cookies(failed)
        return failed
    set_session_cookies(response, session.access_token, session.refresh_token)
    return ok({"user": _user(session.user)})


@router.post("/logout", summary="End this session")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth_service.logout(db, request.cookies.get(REFRESH_COOKIE))
    clear_session_cookies(response)
    return ok({"message": "Logged out."})


@router.post("/logout-all", summary="End every session of the current user")
def logout_all(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service.revoke_all_sessions(db, user.id)
    db.commit()
    clear_session_cookies(response)
    return ok({"message": "Logged out of all devices."})


@router.get("/me", summary="The logged-in user")
def me(user: User = Depends(get_current_user)):
    return ok({"user": _user(user)})


@router.post("/verify-email", summary="Confirm an email address with the emailed token")
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db),
                 limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("20/hour", "verify-email", client_ip(request))
    user = auth_service.verify_email(db, body.token)
    return ok({"user": _user(user)})


@router.post("/resend-verification", status_code=202, summary="Send a new verification email")
def resend_verification(body: EmailIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
                        limiter: RateLimiter = Depends(get_rate_limiter), mailer: EmailSender = Depends(get_email_sender)):
    limiter.hit("5/hour", "resend-ip", client_ip(request))
    limiter.hit("3/hour", "resend-email", auth_service.normalize_email(body.email))
    user, token = auth_service.new_verification_token(db, body.email)
    if user and token:
        background.add_task(mailer.send, verification_email(user.email, token))
    return ok({"message": _CHECK_EMAIL})


@router.post("/forgot-password", status_code=202, summary="Email a password-reset link")
def forgot_password(body: EmailIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
                    limiter: RateLimiter = Depends(get_rate_limiter), mailer: EmailSender = Depends(get_email_sender)):
    limiter.hit("5/hour", "forgot-ip", client_ip(request))
    limiter.hit("3/hour", "forgot-email", auth_service.normalize_email(body.email))
    user, token = auth_service.new_password_reset_token(db, body.email)
    if user and token:
        background.add_task(mailer.send, password_reset_email(user.email, token))
    return ok({"message": _CHECK_EMAIL})


@router.post("/reset-password", summary="Set a new password with the emailed token; ends all sessions")
def reset_password(body: ResetPasswordIn, request: Request, response: Response, db: Session = Depends(get_db),
                   limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("10/hour", "reset-ip", client_ip(request))
    auth_service.reset_password(db, body.token, body.new_password)
    clear_session_cookies(response)
    return ok({"message": "Password updated. Please log in with your new password."})
