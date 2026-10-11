"""Private candidate–admin chat, including the live-interview payment link and token."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.models import (
    LiveInterviewOrder, LiveInterviewToken, SupportMessage, SupportThread, User,
)
from backend.app.services import platform_settings_service as ps
from backend.app.services.payments.base import PaymentError, PaymentProvider


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rupees(cents: int) -> str:
    return f"₹{cents / 100:,.2f}"


def ensure_thread(db: Session, user_id: uuid.UUID) -> SupportThread:
    thread = db.scalar(select(SupportThread).where(SupportThread.user_id == user_id))
    if thread is None:
        thread = SupportThread(user_id=user_id, last_message_at=_now())
        db.add(thread)
        db.flush()
    return thread


def _add_message(
    db: Session, thread: SupportThread, *, sender: str, kind: str, body: str, meta: dict | None = None,
) -> SupportMessage:
    msg = SupportMessage(thread_id=thread.id, sender=sender, kind=kind, body=body, meta=meta or {})
    thread.last_message_at = _now()
    db.add(msg)
    db.flush()
    return msg


def message_out(msg: SupportMessage) -> dict:
    return {
        "id": str(msg.id),
        "sender": msg.sender,
        "kind": msg.kind,
        "body": msg.body,
        "meta": msg.meta or {},
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def thread_out(db: Session, thread: SupportThread, user: User | None = None) -> dict:
    if user is None:
        user = db.get(User, thread.user_id)
    return {
        "id": str(thread.id),
        "user_id": str(thread.user_id),
        "email": user.email if user else "",
        "name": f"{user.first_name} {user.last_name}".strip() if user else "",
        "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else None,
    }


def messages_for(db: Session, thread: SupportThread) -> list[dict]:
    rows = db.scalars(
        select(SupportMessage).where(SupportMessage.thread_id == thread.id).order_by(SupportMessage.created_at)
    ).all()
    codes = [str((m.meta or {}).get("token") or "") for m in rows if m.kind == "token"]
    codes = [code for code in codes if code]
    statuses: dict[str, str] = {}
    if codes:
        for token in db.scalars(select(LiveInterviewToken).where(LiveInterviewToken.code.in_(codes))):
            statuses[token.code] = token.status
    out = []
    for msg in rows:
        data = message_out(msg)
        if msg.kind == "token":
            code = str((msg.meta or {}).get("token") or "")
            data["meta"] = {**data["meta"], "token_status": statuses.get(code, "unused")}
        out.append(data)
    return out


def post_user_message(db: Session, user: User, body: str) -> dict:
    text = body.strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "Write a message first.", 422)
    if len(text) > 4000:
        raise AppError("VALIDATION_ERROR", "Message is too long.", 422)
    thread = ensure_thread(db, user.id)
    msg = _add_message(db, thread, sender="user", kind="text", body=text)
    return {"thread": thread_out(db, thread, user), "message": message_out(msg)}


def post_admin_message(db: Session, thread_id: uuid.UUID, body: str) -> dict:
    text = body.strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "Write a message first.", 422)
    thread = db.get(SupportThread, thread_id)
    if thread is None:
        raise AppError("NOT_FOUND", "That conversation was not found.", 404)
    msg = _add_message(db, thread, sender="admin", kind="text", body=text)
    return {"message": message_out(msg)}


def list_threads(db: Session) -> list[dict]:
    rows = db.scalars(select(SupportThread).order_by(SupportThread.last_message_at.desc())).all()
    return [thread_out(db, t) for t in rows]


def _new_code(db: Session) -> str:
    for _ in range(20):
        code = f"{secrets.randbelow(90_000_000) + 10_000_000:08d}"
        if db.scalar(select(LiveInterviewToken.id).where(LiveInterviewToken.code == code)) is None:
            return code
    raise AppError("TOKEN_EXHAUSTED", "Could not issue a token. Try again.", 503)


def issue_token(db: Session, order: LiveInterviewOrder) -> LiveInterviewToken:
    existing = db.scalar(select(LiveInterviewToken).where(LiveInterviewToken.order_id == order.id))
    if existing is not None:
        return existing
    token = LiveInterviewToken(user_id=order.user_id, order_id=order.id, code=_new_code(db), status="unused")
    db.add(token)
    db.flush()
    return token


def _post_token(db: Session, thread: SupportThread, token: LiveInterviewToken, offer: dict) -> None:
    _add_message(
        db, thread, sender="system", kind="token",
        body=f"Payment received. Your live interview token is {token.code}. Enter it in the desktop agent under Live interview.",
        meta={"token": token.code, "display_name": offer["display_name"]},
    )


def fulfill_order(db: Session, order_id: str) -> bool:
    """Mark a live-interview order paid and post the 8-digit token. Safe to call twice."""
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        return False
    order = db.get(LiveInterviewOrder, oid)
    if order is None:
        return False
    thread = db.get(SupportThread, order.thread_id)
    if thread is None:
        return False
    offer = ps.get_live_interview(db)
    if order.status != "paid":
        order.status = "paid"
    token = issue_token(db, order)
    posted = db.scalars(
        select(SupportMessage).where(SupportMessage.thread_id == thread.id, SupportMessage.kind == "token")
    ).all()
    if not any((m.meta or {}).get("token") == token.code for m in posted):
        _post_token(db, thread, token, offer)
    return True


def request_live_interview(db: Session, user: User, provider: PaymentProvider) -> dict:
    offer = ps.get_live_interview(db)
    if not offer["enabled"]:
        raise AppError("LIVE_INTERVIEW_DISABLED", "Live interview is not available right now.", 403)
    if offer["price_cents"] < 100:
        raise AppError("LIVE_INTERVIEW_DISABLED", "Live interview does not have a price yet.", 403)
    thread = ensure_thread(db, user.id)
    _add_message(
        db, thread, sender="user", kind="text",
        body=f"I'd like a {offer['display_name']} token.",
    )
    order = LiveInterviewOrder(
        user_id=user.id,
        thread_id=thread.id,
        amount_cents=offer["price_cents"],
        currency=offer["currency"],
        provider=provider.name,
        status="pending",
    )
    db.add(order)
    db.flush()
    name = f"{user.first_name} {user.last_name}".strip() or user.email
    try:
        link = provider.create_payment_link(
            amount_cents=offer["price_cents"],
            currency=offer["currency"],
            description=offer["display_name"],
            customer_name=name,
            customer_email=user.email,
            order_id=str(order.id),
        )
    except PaymentError:
        raise
    order.provider_link_id = link.id
    order.provider_link_url = link.url
    if link.status == "paid" or provider.name == "null":
        order.status = "paid"
        token = issue_token(db, order)
        _post_token(db, thread, token, offer)
    else:
        _add_message(
            db, thread, sender="system", kind="payment_link",
            body=f"Pay {_rupees(offer['price_cents'])} for one {offer['display_name']}: {link.url}",
            meta={"url": link.url, "amount_cents": offer["price_cents"], "order_id": str(order.id)},
        )
    return {"thread": thread_out(db, thread, user), "messages": messages_for(db, thread)}
