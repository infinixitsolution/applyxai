"""
Plans, subscriptions, and payments.

A subscription's status only ever comes from the payment provider: from its API after a
signature-checked checkout, or after a signature-checked webhook. Never from the browser.
Switching plans starts the new subscription at once and cancels the old one immediately
(no refund for unused days); the Billing page says so before payment.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.plans import FREE_PLAN, PLAN_LIMITS
from backend.app.models import BillingEvent, Payment, Plan, Subscription, SubscriptionStatus, User
from backend.app.services import notification_service, usage_service
from backend.app.services.payments.base import PaymentProvider, RemotePayment, RemoteSubscription

logger = logging.getLogger("applyxai.billing")

ENTITLED = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
ENDED = (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED)
RECENT_PAYMENTS = 24
PENDING_SHOWN_FOR = timedelta(hours=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return _aware(dt).isoformat() if dt else None


# ----------------------------------------------------------------------------- plans
def seed_plans(db: Session) -> int:
    """Copy the default catalogue into an empty `plans` table. Returns rows added. The caller commits."""
    from backend.app.models.enums import PlanKind

    added = 0
    existing = {p.code: p for p in db.scalars(select(Plan)).all()}
    if not existing:
        for order, (code, plan) in enumerate(PLAN_LIMITS.items()):
            kind = PlanKind.INSTITUTE if plan.get("kind") == "institute" else PlanKind.PERSONAL
            limits = {k: v for k, v in plan.items() if k in ("applications_per_month", "resumes", "seats")}
            db.add(Plan(code=code, name=plan["name"], kind=kind, price_cents=plan["price_cents"], currency="INR",
                        interval="month", limits=limits, sort_order=order))
            added += 1
        db.flush()
        return added
    for order, (code, plan) in enumerate(PLAN_LIMITS.items()):
        if code in existing:
            continue
        kind = PlanKind.INSTITUTE if plan.get("kind") == "institute" else PlanKind.PERSONAL
        limits = {k: v for k, v in plan.items() if k in ("applications_per_month", "resumes", "seats")}
        db.add(Plan(code=code, name=plan["name"], kind=kind, price_cents=plan["price_cents"], currency="INR",
                    interval="month", limits=limits, sort_order=order))
        added += 1
    if added:
        db.flush()
    return added


def get_plan(db: Session, code: str) -> Plan:
    seed_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == code, Plan.is_active.is_(True)))
    if plan is None:
        raise AppError("PLAN_NOT_FOUND", "That plan doesn't exist.", 404)
    return plan


def sync_provider_plans(db: Session, provider: PaymentProvider) -> list[tuple[str, str]]:
    """Create every paid plan at the provider that doesn't have a provider ID yet. The caller commits."""
    seed_plans(db)
    created = []
    for plan in db.scalars(select(Plan).where(Plan.price_cents > 0, Plan.provider_plan_id == "")).all():
        plan.provider_plan_id = provider.create_plan(plan)
        db.flush()
        created.append((plan.code, plan.provider_plan_id))
    return created


def plan_out(plan: Plan) -> dict:
    return {"code": plan.code, "name": plan.name, "price_cents": plan.price_cents,
            "currency": plan.currency, "interval": plan.interval}


def charge_cents(plan: Plan) -> int:
    """What a new subscriber pays: personal plans as listed; campus plans are price × minimum students."""
    from backend.app.models.enums import PlanKind
    seats = int((plan.limits or {}).get("seats") or PLAN_LIMITS.get(plan.code, {}).get("seats") or 1)
    kind = getattr(plan, "kind", None)
    institute = kind == PlanKind.INSTITUTE or getattr(kind, "value", kind) == "institute"
    if not institute:
        institute = PLAN_LIMITS.get(plan.code, {}).get("kind") == "institute"
    return int(plan.price_cents) * seats if institute and seats > 0 else int(plan.price_cents)


# ----------------------------------------------------------------------------- reading
def sub_out(sub: Subscription | None) -> dict | None:
    if sub is None:
        return None
    return {
        "id": str(sub.id), "plan": plan_out(sub.plan), "status": sub.status.value, "provider": sub.provider,
        "current_period_start": _iso(sub.current_period_start), "current_period_end": _iso(sub.current_period_end),
        "cancel_at_period_end": sub.cancel_at_period_end, "created_at": _iso(sub.created_at),
    }


def payment_out(p: Payment) -> dict:
    return {"id": str(p.id), "amount_cents": p.amount_cents, "currency": p.currency, "status": p.status,
            "method": p.method, "description": p.description, "paid_at": _iso(p.paid_at or p.created_at)}


def _entitled(sub: Subscription, now: datetime) -> bool:
    end = _aware(sub.current_period_end)
    return sub.status in ENTITLED and (end is None or end > now)


def current_subscription(db: Session, user_id: uuid.UUID) -> Subscription | None:
    """The paid subscription the user is entitled to right now, if any."""
    now = _now()
    subs = db.scalars(select(Subscription).where(
        Subscription.user_id == user_id, Subscription.institute_id.is_(None), Subscription.status.in_(ENTITLED),
    ).order_by(Subscription.created_at.desc())).all()
    return next((s for s in subs if _entitled(s, now)), None)


def _pending(db: Session, user_id: uuid.UUID) -> Subscription | None:
    """A checkout started in the last hour that the provider hasn't activated yet."""
    return db.scalar(select(Subscription).where(Subscription.user_id == user_id,
                                                Subscription.institute_id.is_(None),
                                                Subscription.status == SubscriptionStatus.PENDING,
                                                Subscription.created_at > _now() - PENDING_SHOWN_FOR)
                     .order_by(Subscription.created_at.desc()).limit(1))


def overview(db: Session, user: User, provider: PaymentProvider) -> dict:
    from backend.app.services.platform_settings_service import get_effective_payments

    payments = db.scalars(select(Payment).where(Payment.user_id == user.id)
                          .order_by(Payment.created_at.desc()).limit(RECENT_PAYMENTS)).all()
    eff = get_effective_payments(db)
    out = {
        "provider": provider.name,
        "subscription": sub_out(current_subscription(db, user.id)),
        "pending": sub_out(_pending(db, user.id)),
        "usage": usage_service.usage_summary(db, user.id),
        "payments": [payment_out(p) for p in payments],
    }
    out["checkout_available"] = eff.configured
    if provider.name == "razorpay":
        out["razorpay_mode"] = eff.razorpay_mode
        out["checkout_live"] = eff.razorpay_mode == "live"
    else:
        out["razorpay_mode"] = None
        out["checkout_live"] = False
    return out


# ----------------------------------------------------------------------------- state changes
def _end_others(db: Session, provider: PaymentProvider, keep: Subscription) -> None:
    """A newly active subscription replaces any other paid one at once."""
    scope = [Subscription.institute_id == keep.institute_id] if keep.institute_id else [
        Subscription.user_id == keep.user_id, Subscription.institute_id.is_(None),
    ]
    others = db.scalars(select(Subscription).where(*scope, Subscription.id != keep.id,
                                                   Subscription.status.in_(ENTITLED + (SubscriptionStatus.PAST_DUE,))
                                                   )).all()
    for old in others:
        if old.provider_subscription_id and old.provider == provider.name:
            provider.cancel_subscription(old.provider_subscription_id, at_period_end=False)
        old.status = SubscriptionStatus.CANCELLED
        old.current_period_end = _now()


def apply_remote(db: Session, provider: PaymentProvider, sub: Subscription, remote: RemoteSubscription) -> None:
    """Bring `sub` in line with what the provider reports, with the side effects of each change."""
    before = sub.status
    if before in ENDED and remote.status not in ENDED:
        logger.info("Ignoring %s for ended subscription %s", remote.raw_status, sub.id)
        return
    sub.status = remote.status
    if remote.current_start:
        sub.current_period_start = remote.current_start
    if remote.current_end:
        sub.current_period_end = remote.current_end
    if remote.customer_id:
        sub.provider_customer_id = remote.customer_id[:255]
    db.flush()
    if sub.status == before:
        return
    name = sub.plan.name
    if sub.status in ENTITLED:
        _end_others(db, provider, sub)
        if sub.institute_id:
            from backend.app.services import institute_service
            institute_service.ensure_seats_for_subscription(db, sub)
        limit = usage_service.plan_limits(db, sub.user_id)["applications_per_month"]
        notification_service.notify_event(
            db, sub.user_id, "plan_active", link="/billing",
            variables={
                "plan_name": name,
                "message": f"You can now send up to {limit:,} applications a month.",
            },
        )
    elif sub.status == SubscriptionStatus.PAST_DUE and before in ENTITLED:
        notification_service.notify_event(
            db, sub.user_id, "payment_failed", link="/billing",
            variables={
                "plan_name": name,
                "message": (
                    f"We couldn't renew your {name} plan. Check your payment method with your bank "
                    "or card provider; you're on the Free plan until a payment succeeds."
                ),
            },
        )
    elif sub.status in ENDED and before in ENTITLED + (SubscriptionStatus.PAST_DUE,):
        notification_service.notify_event(
            db, sub.user_id, "plan_ended", link="/billing",
            variables={"plan_name": name, "message": "You're on the Free plan now. You can subscribe again at any time."},
        )


def record_payment(db: Session, provider: PaymentProvider, user_id: uuid.UUID, sub: Subscription | None,
                   remote: RemotePayment) -> Payment:
    """Insert or update a payment by its provider ID (safe to repeat). The caller commits."""
    for _ in range(2):
        payment = db.scalar(select(Payment).where(Payment.provider_payment_id == remote.id))
        if payment is not None:
            break
        try:
            with db.begin_nested():
                payment = Payment(user_id=user_id, subscription_id=sub.id if sub else None, provider=provider.name,
                                  provider_payment_id=remote.id[:255])
                db.add(payment)
            break
        except IntegrityError:
            continue
    if payment.user_id != user_id:
        raise AppError("PAYMENT_MISMATCH", "That payment belongs to another account.", 409)
    payment.amount_cents, payment.currency = remote.amount_cents, remote.currency
    payment.status, payment.method = remote.status, remote.method
    payment.description = remote.description or (f"{sub.plan.name} plan" if sub else "")
    payment.paid_at = remote.created_at or payment.paid_at
    db.flush()
    if sub is not None and sub.institute_id:
        from backend.app.services import partner_service
        partner_service.maybe_accrue_commission(db, payment, sub)
    return payment


# ----------------------------------------------------------------------------- user actions
def checkout(db: Session, user: User, provider: PaymentProvider, plan_code: str,
             institute_id: uuid.UUID | None = None) -> dict:
    from backend.app.models.enums import PlanKind
    from backend.app.core.plans import is_public_checkout_plan

    plan = get_plan(db, plan_code)
    if not is_public_checkout_plan(plan.code):
        raise AppError("PLAN_NOT_AVAILABLE", "That plan is not available for self-service checkout.", 400)
    wanted = PlanKind.INSTITUTE if institute_id else PlanKind.PERSONAL
    if getattr(plan, "kind", PlanKind.PERSONAL) != wanted:
        raise AppError("WRONG_PLAN_KIND", "That plan is not available for this workspace.", 400)
    if plan.price_cents <= 0 or plan.code == FREE_PLAN:
        raise AppError("FREE_PLAN", "The Free plan doesn't need a subscription. Cancel your paid plan to go back to it.", 400)
    if institute_id:
        from backend.app.services import institute_service
        current = institute_service.current_subscription(db, institute_id)
    else:
        current = current_subscription(db, user.id)
    if current is not None and current.plan_id == plan.id:
        raise AppError("ALREADY_SUBSCRIBED", f"You're already on the {plan.name} plan.", 409)
    if provider.name == "null" and not settings.PAYMENT_DEV_INSTANT_CHECKOUT:
        raise AppError(
            "CHECKOUT_DISABLED",
            "Razorpay checkout is not enabled. An admin must open Settings → Payments, choose Razorpay, "
            "save test or live API keys, then Sync plans to Razorpay.",
            503,
        )
    if provider.name == "razorpay" and not (plan.provider_plan_id or "").strip():
        raise AppError(
            "PLAN_NOT_AVAILABLE",
            f"The {plan.name} plan is not linked to Razorpay yet. An admin must run Sync plans to Razorpay in Settings → Payments.",
            503,
        )
    replaces = sub_out(current)
    # Earlier unfinished checkouts stay pending: if one is paid after all, it still activates.
    remote = provider.create_subscription(plan, user)
    sub = Subscription(user_id=user.id, institute_id=institute_id, plan_id=plan.id, plan=plan,
                       status=SubscriptionStatus.PENDING, provider=provider.name,
                       provider_subscription_id=remote.id[:255],
                       provider_customer_id=remote.customer_id[:255])
    db.add(sub)
    db.flush()
    apply_remote(db, provider, sub, remote)
    return {"subscription": sub_out(sub), "checkout": provider.checkout_options(remote.id, plan, user),
            "replaces": replaces}


def _own_subscription(db: Session, user_id: uuid.UUID, provider_subscription_id: str) -> Subscription:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id,
                                               Subscription.provider_subscription_id == provider_subscription_id))
    if sub is None:
        raise AppError("NOT_FOUND", "Subscription not found", 404)
    return sub


def confirm_checkout(db: Session, user: User, provider: PaymentProvider, *,
                     payment_id: str, subscription_id: str, signature: str) -> dict:
    confirmed = provider.verify_checkout(payment_id, subscription_id, signature)
    sub = _own_subscription(db, user.id, confirmed.subscription_id)
    apply_remote(db, provider, sub, provider.fetch_subscription(confirmed.subscription_id))
    record_payment(db, provider, user.id, sub, provider.fetch_payment(confirmed.payment_id))
    return {"subscription": sub_out(sub)}


def cancel(db: Session, user: User, provider: PaymentProvider) -> dict:
    sub = current_subscription(db, user.id)
    if sub is None:
        raise AppError("NO_SUBSCRIPTION", "You're on the Free plan; there's nothing to cancel.", 404)
    if sub.provider != provider.name:
        # A complimentary plan from an admin: nothing is charged, and it ends by itself.
        raise AppError("COMPLIMENTARY_PLAN", "This plan was given to you by ApplyXAI and ends by itself. "
                       "You won't be charged.", 409)
    if not sub.cancel_at_period_end:
        remote = provider.cancel_subscription(sub.provider_subscription_id or "", at_period_end=True)
        sub.cancel_at_period_end = True
        apply_remote(db, provider, sub, remote)
        until = sub.current_period_end
        period = _aware(until).strftime("%d %b %Y") if until else "the end of this billing period"
        notification_service.notify_event(
            db,
            user.id,
            "plan_cancelled",
            link="/billing",
            variables={
                "plan_name": sub.plan.name,
                "message": f"It stays active until {period}. You won't be charged again.",
            },
        )
    return {"subscription": sub_out(sub)}


# ----------------------------------------------------------------------------- webhooks
def handle_webhook(db: Session, provider: PaymentProvider, headers: dict[str, str], body: bytes) -> dict:
    """
    Verify, deduplicate, then re-read the subscription from the provider (webhooks can arrive
    out of order, so their payload only says *that* something changed). The caller commits; on
    any error nothing is committed and the provider retries.
    """
    event = provider.parse_webhook(headers, body)
    event_id = event.id[:255]
    seen = select(BillingEvent.id).where(BillingEvent.provider == provider.name, BillingEvent.event_id == event_id)
    if db.scalar(seen) is not None:
        return {"duplicate": True}

    # The event is recorded last, so a failure above leaves it unrecorded for the provider's retry.
    # Two deliveries racing here are harmless: applying is idempotent and the insert is unique.
    record = BillingEvent(provider=provider.name, event_id=event_id, event_type=event.type)
    sub = None
    if event.subscription_id:
        sub = db.scalar(select(Subscription).where(Subscription.provider == provider.name,
                                                   Subscription.provider_subscription_id == event.subscription_id))
    if sub is not None:
        record.user_id, record.subscription_id = sub.user_id, sub.id
        apply_remote(db, provider, sub, provider.fetch_subscription(event.subscription_id))
        if event.payment is not None:
            record_payment(db, provider, sub.user_id, sub, event.payment)
    else:
        logger.info("Webhook %s (%s) matches no subscription; recorded only", event_id, event.type)
    db.add(record)
    db.flush()
    return {"duplicate": False, "matched": sub is not None}
