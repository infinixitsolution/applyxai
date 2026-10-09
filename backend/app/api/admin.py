"""Admin endpoints. Every route requires an admin session; non-admins get 403."""

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_mailer, require_admin
from backend.app.core.cookies import set_session_cookies
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import ApplicationStatus, SubscriptionStatus, User
from backend.app.schemas.admin import (
    BroadcastNotificationsIn,
    GrantPlanIn,
    InstituteCreateIn,
    InstituteUpdateIn,
    PartnerCreateIn,
    PartnerUpdateIn,
    PlanUpdateIn,
    TestEmailIn,
    TestTemplateIn,
    UserCreateIn,
    UserUpdateIn,
)
from backend.app.schemas.institute import PasswordIn
from backend.app.schemas.platform_settings import AiIn, AuthEmailIn, CmsIn, EmailTemplatesIn, NotificationsIn, PaymentsIn, SmtpIn
from backend.app.services import ai_service
from backend.app.services.ai_service import AiTask
from backend.app.services import admin_service, auth_service, platform_settings_service as ps
from backend.app.services.email_service import EmailSender, sample_email, verification_email
from backend.app.services import billing_service
from backend.app.services.payments import PaymentProvider, get_payment_provider, resolve_payment_provider
from backend.app.services.payments.base import PaymentError

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


@router.post("/users", summary="Create a user account")
def create_user(body: UserCreateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = admin_service.create_user(db, admin, **body.model_dump())
    db.commit()
    return ok(result)


@router.get("/users/{user_id}", summary="One user's account, plan, usage, runs, and computers")
def user_detail(user_id: uuid.UUID, db: Session = Depends(get_db)):
    return ok(admin_service.user_detail(db, user_id))


@router.patch("/users/{user_id}", summary="Update a user's profile and access")
def update_user(user_id: uuid.UUID, body: UserUpdateIn, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    result = admin_service.update_user(db, admin, user_id, **body.model_dump(exclude_unset=True))
    db.commit()
    return ok(result)


@router.delete("/users/{user_id}", summary="Permanently delete a user account")
def delete_user(user_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    admin_service.delete_user(db, admin, user_id)
    db.commit()
    return ok({"ok": True})


@router.post("/users/{user_id}/password", summary="Set a new password for a user")
def user_password(user_id: uuid.UUID, body: PasswordIn, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    result = admin_service.set_user_password(db, admin, user_id, body.password)
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


@router.put("/settings/email-templates", summary="Auth and notification email/in-app templates")
def put_settings_email_templates(body: EmailTemplatesIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                                 limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    templates = ps.update_email_templates(db, body)
    admin_service.audit_settings(db, admin, "settings.email_templates", {"auth": list(body.auth.keys())})
    db.commit()
    return ok({"email_templates": templates})


@router.post("/email/test-template", summary="Send a sample auth template email")
def email_test_template(body: TestTemplateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                        limiter: RateLimiter = Depends(get_rate_limiter), mailer: EmailSender = Depends(get_mailer)):
    limiter.hit("10/hour", "admin-test-email", str(admin.id))
    result = admin_service.send_test_template(db, admin, mailer, body.kind, str(body.to or admin.email))
    db.commit()
    return ok(result)


@router.post("/notifications/broadcast", summary="Send an in-app notification to selected users")
def notifications_broadcast(body: BroadcastNotificationsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                            limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("10/hour", "admin-broadcast", str(admin.id))
    try:
        ids = [uuid.UUID(x) for x in body.user_ids]
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", "Invalid user id in list.", 422) from exc
    result = admin_service.broadcast_notifications(
        db, admin, title=body.title.strip(), body=body.body.strip(), link=body.link.strip(), user_ids=ids,
    )
    db.commit()
    return ok(result)


@router.put("/settings/payments", summary="Razorpay keys and payment mode")
def put_settings_payments(body: PaymentsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                          limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    payments = ps.update_payments(db, body)
    admin_service.audit_settings(db, admin, "settings.payments", {"provider": payments.get("provider")})
    db.commit()
    return ok({"payments": payments})


@router.post("/settings/payments/test", summary="Verify Razorpay API keys")
def post_settings_payments_test(admin: User = Depends(require_admin), db: Session = Depends(get_db),
                                limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("20/hour", "admin-payments-test", str(admin.id))
    provider = resolve_payment_provider(db)
    if provider.name != "razorpay":
        raise AppError("PAYMENTS_NOT_CONFIGURED", "Set Razorpay as the provider and save Key ID + secret first.", 503)
    try:
        result = provider.verify_credentials()
    except PaymentError as exc:
        raise AppError(exc.code, exc.message, exc.status_code) from None
    admin_service.audit_settings(db, admin, "settings.payments_test", {"ok": True, "mode": result.get("mode")})
    db.commit()
    return ok(result)


@router.post("/settings/payments/sync-plans", summary="Create paid plans at Razorpay")
def post_settings_payments_sync_plans(admin: User = Depends(require_admin), db: Session = Depends(get_db),
                                      limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("10/hour", "admin-payments-sync", str(admin.id))
    provider = resolve_payment_provider(db)
    if provider.name != "razorpay":
        raise AppError("PAYMENTS_NOT_CONFIGURED", "Configure Razorpay before syncing plans.", 503)
    created = billing_service.sync_provider_plans(db, provider)
    admin_service.audit_settings(db, admin, "settings.payments_sync", {"created": len(created)})
    db.commit()
    return ok({"created": [{"code": c, "provider_plan_id": pid} for c, pid in created]})


@router.put("/settings/ai", summary="Platform AI provider, models, and API key")
def put_settings_ai(body: AiIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                    limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "admin-settings", str(admin.id))
    ai = ps.update_ai(db, body)
    admin_service.audit_settings(db, admin, "settings.ai", {"enabled": ai.get("enabled"), "provider": ai.get("provider")})
    db.commit()
    return ok({"ai": ai})


@router.post("/settings/ai/test", summary="Verify the configured AI provider responds")
def post_settings_ai_test(admin: User = Depends(require_admin), db: Session = Depends(get_db),
                          limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("20/hour", "admin-ai-test", str(admin.id))
    try:
        reply = ai_service.complete(
            db,
            AiTask.TEST,
            system="You are a connectivity check. Reply with exactly OK.",
            user="Ping",
            feature="applications",
            max_tokens=16,
        )
        ok_reply = reply.strip().upper().startswith("OK")
        admin_service.audit_settings(db, admin, "settings.ai_test", {"ok": ok_reply})
        db.commit()
        return ok({"ok": ok_reply, "reply": reply[:200]})
    except Exception as exc:
        from backend.app.core.errors import AppError

        if isinstance(exc, AppError):
            raise
        raise AppError("AI_ERROR", str(exc), 502) from exc


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


@router.get("/institutes")
def institutes(q: str | None = Query(None, max_length=200), status: str | None = None,
               params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    from backend.app.models import InstituteStatus
    from backend.app.services import institute_service
    try:
        st = InstituteStatus(status) if status else None
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown institute status.", 422)
    return ok(institute_service.list_institutes(db, params, q=q, status=st))


@router.post("/institutes", summary="Create an institute and its admin login")
def create_institute(body: InstituteCreateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from backend.app.services import institute_service
    institute = institute_service.create_by_admin(db, **body.model_dump())
    admin_service._audit(db, admin, "institute.create", None, target_label=institute.name, email=institute.email)
    db.commit()
    return ok(institute_service.institute_out(db, institute))


@router.get("/institutes/{institute_id}")
def institute_detail(institute_id: uuid.UUID, db: Session = Depends(get_db)):
    from backend.app.services import institute_service
    institute = institute_service.get_institute(db, institute_id)
    return ok(institute_service.admin_detail(db, institute))


@router.put("/institutes/{institute_id}")
def update_institute(institute_id: uuid.UUID, body: InstituteUpdateIn, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    from backend.app.services import institute_service
    institute = institute_service.get_institute(db, institute_id)
    institute_service.update_by_admin(db, institute, **body.model_dump())
    admin_service._audit(db, admin, "institute.update", None, target_label=institute.name)
    db.commit()
    return ok(institute_service.institute_out(db, institute))


@router.post("/institutes/{institute_id}/status")
def institute_status(institute_id: uuid.UUID, body: dict, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    from backend.app.models import InstituteStatus
    from backend.app.services import institute_service
    institute = institute_service.get_institute(db, institute_id)
    try:
        status = InstituteStatus(str(body.get("status") or ""))
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown institute status.", 422)
    institute_service.set_status(db, institute, status)
    admin_service._audit(db, admin, "institute.status", None, target_label=institute.name, status=status.value)
    db.commit()
    return ok(institute_service.institute_out(db, institute))


@router.post("/institutes/{institute_id}/password")
def institute_password(institute_id: uuid.UUID, body: PasswordIn, admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    from backend.app.core.security import hash_password
    from backend.app.services import institute_service
    institute = institute_service.get_institute(db, institute_id)
    user = institute_service.admin_user(db, institute)
    if user is None:
        raise AppError("NO_ADMIN", "This institute has no admin user.", 400)
    user.password_hash = hash_password(body.password)
    admin_service._audit(db, admin, "institute.password", user)
    db.commit()
    return ok({"ok": True})


@router.post("/institutes/{institute_id}/login-as")
def institute_login_as(institute_id: uuid.UUID, response: Response, admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    from backend.app.services import institute_service
    institute = institute_service.get_institute(db, institute_id)
    user = institute_service.admin_user(db, institute)
    if user is None:
        raise AppError("NO_ADMIN", "This institute has no admin user.", 400)
    session = auth_service._start_session(db, user)
    admin_service._audit(db, admin, "institute.login_as", user, target_label=institute.name)
    db.commit()
    set_session_cookies(response, session.access_token, session.refresh_token)
    from backend.app.services.workspace import user_payload
    return ok({"user": user_payload(db, user)})


@router.get("/partners")
def partners(q: str | None = Query(None, max_length=200), status: str | None = None,
             params: PageParams = Depends(page_params), db: Session = Depends(get_db)):
    from backend.app.models import PartnerStatus
    from backend.app.services import partner_service
    try:
        st = PartnerStatus(status) if status else None
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown partner status.", 422)
    return ok(partner_service.list_partners(db, params, q=q, status=st))


@router.post("/partners", summary="Create a partner and its login")
def create_partner(body: PartnerCreateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from backend.app.services import partner_service
    partner = partner_service.create_by_admin(db, **body.model_dump())
    admin_service._audit(db, admin, "partner.create", None, target_label=partner.organization, email=body.email)
    db.commit()
    return ok(partner_service.partner_out(db, partner))


@router.get("/partners/{partner_id}")
def partner_detail(partner_id: uuid.UUID, db: Session = Depends(get_db)):
    from backend.app.services import partner_service
    partner = partner_service.get_partner(db, partner_id)
    return ok(partner_service.admin_detail(db, partner))


@router.put("/partners/{partner_id}")
def update_partner(partner_id: uuid.UUID, body: PartnerUpdateIn, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    from backend.app.services import partner_service
    partner = partner_service.get_partner(db, partner_id)
    partner_service.update_by_admin(db, partner, **body.model_dump())
    admin_service._audit(db, admin, "partner.update", None, target_label=partner.organization)
    db.commit()
    return ok(partner_service.partner_out(db, partner))


@router.post("/partners/{partner_id}/status")
def partner_status(partner_id: uuid.UUID, body: dict, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    from backend.app.models import PartnerStatus
    from backend.app.services import partner_service
    partner = partner_service.get_partner(db, partner_id)
    try:
        status = PartnerStatus(str(body.get("status") or ""))
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown partner status.", 422)
    partner_service.set_status(db, partner, status)
    admin_service._audit(db, admin, "partner.status", None, target_label=partner.organization, status=status.value)
    db.commit()
    return ok(partner_service.partner_out(db, partner))


@router.post("/partners/{partner_id}/kyc")
def partner_kyc(partner_id: uuid.UUID, body: dict, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    from backend.app.models import KycStatus
    from backend.app.services import partner_service
    partner = partner_service.get_partner(db, partner_id)
    try:
        status = KycStatus(str(body.get("status") or ""))
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown KYC status.", 422)
    partner_service.set_kyc(db, partner, status)
    admin_service._audit(db, admin, "partner.kyc", None, target_label=partner.organization, status=status.value)
    db.commit()
    return ok(partner_service.partner_out(db, partner))


@router.post("/partners/{partner_id}/password")
def partner_password(partner_id: uuid.UUID, body: PasswordIn, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    from backend.app.core.security import hash_password
    from backend.app.services import partner_service
    partner = partner_service.get_partner(db, partner_id)
    user = partner_service.partner_user(db, partner)
    if user is None:
        raise AppError("NO_USER", "This partner has no login.", 400)
    user.password_hash = hash_password(body.password)
    admin_service._audit(db, admin, "partner.password", user)
    db.commit()
    return ok({"ok": True})


@router.post("/partners/{partner_id}/login-as")
def partner_login_as(partner_id: uuid.UUID, response: Response, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    from backend.app.services import partner_service
    from backend.app.services.workspace import user_payload
    partner = partner_service.get_partner(db, partner_id)
    user = partner_service.partner_user(db, partner)
    if user is None:
        raise AppError("NO_USER", "This partner has no login.", 400)
    session = auth_service._start_session(db, user)
    admin_service._audit(db, admin, "partner.login_as", user, target_label=partner.organization)
    db.commit()
    set_session_cookies(response, session.access_token, session.refresh_token)
    return ok({"user": user_payload(db, user)})


@router.post("/commissions/{commission_id}/status")
def commission_status(commission_id: uuid.UUID, body: dict, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    from backend.app.models import CommissionStatus
    from backend.app.services import partner_service
    try:
        status = CommissionStatus(str(body.get("status") or ""))
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown commission status.", 422)
    row = partner_service.set_commission_status(db, commission_id, status)
    admin_service._audit(db, admin, "commission.status", None, target_label=str(commission_id), status=status.value)
    db.commit()
    return ok(partner_service.commission_out(row))


@router.post("/payouts/{payout_id}/status")
def payout_status(payout_id: uuid.UUID, body: dict, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    from backend.app.models import PayoutStatus
    from backend.app.services import partner_service
    try:
        status = PayoutStatus(str(body.get("status") or ""))
    except ValueError:
        raise AppError("INVALID_STATUS", "Unknown payout status.", 422)
    row = partner_service.set_payout_status(db, payout_id, status, str(body.get("note") or ""))
    admin_service._audit(db, admin, "payout.status", None, target_label=str(payout_id), status=status.value)
    db.commit()
    return ok(partner_service.payout_out(row))