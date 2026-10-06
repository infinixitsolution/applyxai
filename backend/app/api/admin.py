"""Admin endpoints. Every route requires an admin session; non-admins get 403."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import require_admin
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.models import ApplicationStatus, AutomationStatus, SubscriptionStatus, User
from backend.app.schemas.admin import GrantPlanIn, PlanUpdateIn, UserUpdateIn
from backend.app.services import admin_service
from backend.app.services.payments import PaymentProvider, get_payment_provider

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

LogLevel = Literal["info", "warning", "error"]


@router.get("/analytics", summary="Users, revenue, applications, and runs at a glance")
def analytics(db: Session = Depends(get_db)):
    return ok(admin_service.analytics(db))


@router.get("/users", summary="All users")
def users(q: str | None = Query(None, max_length=200),
          status: Literal["active", "disabled", "admin"] | None = None,
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


@router.get("/plans", summary="Plan catalogue, including inactive plans")
def plans(db: Session = Depends(get_db)):
    return ok({"plans": admin_service.list_plans(db)})


@router.put("/plans/{code}", summary="Edit a plan's name, price, limits, and visibility")
def update_plan(code: str, body: PlanUpdateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                provider: PaymentProvider = Depends(get_payment_provider)):
    result = admin_service.update_plan(db, admin, provider, code, **body.model_dump())
    db.commit()
    return ok(result)
