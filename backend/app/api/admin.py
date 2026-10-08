"""Admin endpoints. Every route requires an admin session; non-admins get 403."""

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_mailer, require_admin
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import ApplicationStatus, SubscriptionStatus, User
from backend.app.schemas.admin import GrantPlanIn, PlanUpdateIn, TestEmailIn, UserUpdateIn
from backend.app.schemas.platform_settings import AuthEmailIn, CmsIn, NotificationsIn, SmtpIn
from backend.app.services import admin_service, platform_settings_service as ps
from backend.app.services.email_service import EmailSender, sample_email, verification_email
from backend.app.services.payments import PaymentProvider, get_payment_provider

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

LogLevel = Literal["info", "warning", "error"]


@router.get("/analytics", summary="Users, revenue, applications, and runs at a glance")
def analytics(db: Session = Depends(get_db)):
    return ok(admin_service.analytics(db))


@router.get("/users", summary="All users")
def users(q: str | None = Query(None, max_length=200),
          status: Literal["active", "disabled", "admin", "unverified"] | None = None,
          plan: str | None = Query(None, max_length=32),
          params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(admin_service.list_users(db, params, q=q, status=status, plan=plan))


@router.get("/users/{user_id}", summary="One user's account, plan, usage, runs, and computers")
def user_detail(user_id: uuid.UUID, db: Session = Depends(get_db)):
    return ok(admin_service.user_detail(db, user_id))


@router.patch("/users/{user_id}", summary="Disable / enable a user, or change admin access")
def update_user(user_id: uuid.UUID, body: UserUpdateIn, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    result = admin_service.update_user(db, admin, user_id, is_active=body.is_active, is_admin=body.is_admin)
    db.commit()
    return ok(result)


@router.post("/users/{user_id}/grant-plan", summary="Give a complimentary plan (no payment)")
def grant_plan(user_id: uuid.UUID, body: GrantPlanIn, admin: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    result = admin_service.grant_plan(db, admin, user_id, body.plan, body.months, body.note)
    db.commit()
    return ok(result)


@router.post("/users/{user_id}/revoke-plan", summary="End a complimentary plan now")
def revoke_plan(user_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = admin_service.revoke_grant(db, admin, user_id)
    db.commit()
    return ok(result)


@router.get("/subscriptions", summary="All subscriptions")
def subscriptions(status: SubscriptionStatus | None = None, plan: str | None = Query(None, max_length=32),
                  params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(admin_service.list_subscriptions(db, params, status=status.value if status else None, plan=plan))


@router.get("/automation-jobs", summary="All automation runs")
def automation_jobs(status: Literal["active", "queued", "running", "paused", "completed", "failed", "cancelled"] | None = None,
                    params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(admin_service.list_runs(db, params, status=status))


@router.post("/automation-jobs/{run_id}/stop", summary="Stop a user's run after its current job")
def stop_run(run_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = admin_service.stop_run(db, admin, run_id)
    db.commit()
    return ok(result)


@router.get("/applications", summary="Applications across all users")
def applications(status: ApplicationStatus | None = None, q: str | None = Query(None, max_length=200),
                 params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(admin_service.list_applications(db, params, status=status.value if status else None, q=q))


@router.get("/logs", summary="Automation log lines across all runs")
def logs(level: list[LogLevel] = Query(default=["warning", "error"]), q: str | None = Query(None, max_length=200),
         params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(admin_service.list_logs(db, params, levels=list(level), q=q))


@router.get("/audit-log", summary="Changes made by admins")
def audit_log(params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    return ok(admin_service.list_audit(db, params))


@router.get("/workers", summary="Background worker and desktop agent status")
def workers(db: Session = Depends(get_db)):
    return ok(admin_service.workers(db))


@router.get("/settings", summary="Platform settings (CMS, SMTP, auth email, notifications, infrastructure)")
def get_settings(db: Session = Depends(get_db)):
    return ok(admin_service.settings_overview(db))


@router.put("/settings/cms", summary="Replace public site content")
def put_settings_cms(body: CmsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                       limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    cms = ps.update_cms(db, body)
    admin_service.audit_settings(db, admin, "settings.cms", {"updated": True})
    db.commit()
    return ok({"cms": cms})


@router.put("/settings/smtp", summary="Save SMTP delivery settings")
def put_settings_smtp(body: SmtpIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                      limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    smtp = ps.update_smtp(db, body)
    admin_service.audit_settings(db, admin, "settings.smtp", {"host": smtp.get("host", "")})
    db.commit()
    return ok({"smtp": smtp})


@router.put("/settings/auth-email", summary="Email verification and link settings")
def put_settings_auth_email(body: AuthEmailIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                            limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    auth = ps.update_auth_email(db, body)
    admin_service.audit_settings(db, admin, "settings.auth_email", auth)
    db.commit()
    return ok({"auth_email": auth})


@router.put("/settings/notifications", summary="Per-event email notification toggles")
def put_settings_notifications(body: NotificationsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                               limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    notifications = ps.update_notifications(db, body)
    admin_service.audit_settings(db, admin, "settings.notifications", {"types": list(body.types.keys())})
    db.commit()
    return ok({"notifications": notifications})


@router.get("/email", summary="How email is delivered (never the SMTP password), and unverified accounts")
def email_status(db: Session = Depends(get_db)):
    return ok(admin_service.email_overview(db))


@router.post("/email/test", summary="Send a test email now and report whether it was accepted")
def email_test(body: TestEmailIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
               limiter: RateLimiter = Depends(get_rate_limiter), mailer: EmailSender = Depends(get_mailer)):
    limiter.hit("10/hour", "admin-test-email", str(admin.id))
    result = admin_service.send_test_email(db, admin, mailer, str(body.to or admin.email))
    db.commit()
    return ok(result)


@router.post("/users/{user_id}/verify-email", summary="Mark a user's email address as verified")
def verify_email(user_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = admin_service.mark_verified(db, admin, user_id)
    db.commit()
    return ok(result)


@router.post("/users/{user_id}/resend-verification", summary="Email the user a new verification link")
def resend_verification(user_id: uuid.UUID, background: BackgroundTasks, admin: User = Depends(require_admin),
                        db: Session = Depends(get_db), mailer: EmailSender = Depends(get_mailer)):
    result, token = admin_service.resend_verification(db, admin, user_id)
    db.commit()
    background.add_task(mailer.send, verification_email(result["user"]["email"], token, db))
    return ok(result)


@router.get("/plans", summary="Plan catalogue, including inactive plans")
def plans(db: Session = Depends(get_db)):
    return ok({"plans": admin_service.list_plans(db)})


@router.put("/plans/{code}", summary="Edit a plan's name, price, limits, and visibility")
def update_plan(code: str, body: PlanUpdateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                provider: PaymentProvider = Depends(get_payment_provider)):
    result = admin_service.update_plan(db, admin, provider, code, **body.model_dump())
    db.commit()
    return ok(result)
