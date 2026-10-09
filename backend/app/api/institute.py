import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_mailer, require_institute_member
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.core.plans import PLAN_LIMITS
from backend.app.models import AssignmentStatus, Plan, PlanKind, User
from backend.app.schemas.institute import InstituteProfileIn, InstituteSettingsIn, InviteIn
from backend.app.services import billing_service, institute_service
from backend.app.services.email_service import EmailSender, institute_invite_email
from backend.app.services.payments import get_payment_provider

router = APIRouter(prefix="/institute", tags=["institute"])


@router.get("/me")
def me(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    user, institute, member = ctx
    return ok({"institute": institute_service.institute_out(db, institute), "role": member.role.value})


@router.get("/dashboard")
def dashboard(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok(institute_service.dashboard(db, institute))


@router.get("/students")
def students(status: AssignmentStatus | None = None, params: PageParams = Depends(page_params),
             ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok(institute_service.list_assignments(db, institute, params, status=status))


@router.post("/students/invite")
def invite(body: InviteIn, background: BackgroundTasks, ctx=Depends(require_institute_member),
           db: Session = Depends(get_db), mailer: EmailSender = Depends(get_mailer)):
    user, institute, _member = ctx
    assignment, token = institute_service.invite_candidate(db, institute, body.email, user, body.note)
    institute_service.notify_candidate_invited(db, institute, body.email, token)
    db.commit()
    background.add_task(mailer.send, institute_invite_email(body.email, institute.name, token, db))
    return ok({"assignment": institute_service.assignment_out(assignment)})


@router.post("/students/{assignment_id}/release")
def release(assignment_id: uuid.UUID, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    row = institute_service.release_assignment(db, institute, assignment_id)
    db.commit()
    return ok({"assignment": institute_service.assignment_out(row)})


@router.post("/students/{assignment_id}/suspend")
def suspend(assignment_id: uuid.UUID, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    row = institute_service.suspend_assignment(db, institute, assignment_id)
    db.commit()
    return ok({"assignment": institute_service.assignment_out(row)})


@router.get("/invitations")
def invitations(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok({"items": institute_service.list_invites(db, institute)})


@router.get("/seats")
def seats(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok({"items": institute_service.list_seats(db, institute), "counts": institute_service.seat_counts(db, institute.id)})


@router.get("/plans")
def plans(db: Session = Depends(get_db)):
    billing_service.seed_plans(db)
    rows = db.scalars(select(Plan).where(Plan.is_active.is_(True), Plan.kind == PlanKind.INSTITUTE)
                      .order_by(Plan.sort_order, Plan.price_cents)).all()
    if not rows:
        items = [{"code": code, "name": p["name"], "price_cents": p["price_cents"], "currency": "INR",
                  "interval": "month", "limits": {"seats": p.get("seats", 0),
                                                 "applications_per_month": p.get("applications_per_month", 0),
                                                 "resumes": p.get("resumes", 0)}}
                 for code, p in PLAN_LIMITS.items() if p.get("kind") == "institute"]
    else:
        items = [{"code": p.code, "name": p.name, "price_cents": p.price_cents, "currency": p.currency,
                  "interval": p.interval, "limits": {**PLAN_LIMITS.get(p.code, {}), **(p.limits or {})}}
                 for p in rows]
    return ok({"plans": items})


@router.get("/subscription")
def subscription(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok({"subscription": billing_service.sub_out(institute_service.current_subscription(db, institute.id)),
               "seats": institute_service.seat_counts(db, institute.id)})


@router.post("/subscription/checkout")
def checkout(body: dict, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    user, institute, member = ctx
    institute_service.require_active(institute)
    institute_service.require_admin_member(member)
    provider = get_payment_provider(db)
    result = billing_service.checkout(db, user, provider, str(body.get("plan") or ""), institute_id=institute.id)
    db.commit()
    return ok(result)


@router.get("/reports")
def reports(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok(institute_service.reports(db, institute))


@router.get("/profile")
def get_profile(ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, _member = ctx
    return ok(institute_service.institute_out(db, institute))


@router.put("/profile")
def put_profile(body: InstituteProfileIn, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, member = ctx
    institute_service.require_admin_member(member)
    institute_service.save_profile(db, institute, body.model_dump(exclude_none=True))
    db.commit()
    return ok(institute_service.institute_out(db, institute))


@router.put("/settings")
def put_settings(body: InstituteSettingsIn, ctx=Depends(require_institute_member), db: Session = Depends(get_db)):
    _user, institute, member = ctx
    institute_service.require_admin_member(member)
    institute_service.save_settings(db, institute, body.model_dump(exclude_none=True))
    db.commit()
    return ok(institute_service.institute_out(db, institute))


invites = APIRouter(prefix="/invites", tags=["invites"])


@invites.get("/{token}")
def preview_invite(token: str, db: Session = Depends(get_db)):
    return ok(institute_service.invite_preview(db, token))


@invites.post("/{token}/accept")
def accept_invite(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = institute_service.accept_invite(db, user, token)
    db.commit()
    return ok({"assignment": institute_service.assignment_out(row)})
