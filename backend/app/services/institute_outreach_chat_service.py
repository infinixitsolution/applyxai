"""WhatsApp chat threads with institute leads after outreach."""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, page_response
from backend.app.models.outreach import InstituteLead, InstituteLeadChatMessage
from backend.app.services import whatsapp_bridge_client

logger = logging.getLogger("applyxai.outreach.chat")

_CHAT_BRIDGE_SYNC_AT: dict[uuid.UUID, float] = {}
_CHAT_SYNC_COOLDOWN_SEC = 2.5
_CONSOLIDATE_LAST_AT = 0.0
_CONSOLIDATE_COOLDOWN_SEC = 120.0


def _maybe_consolidate_junk_leads(db: Session) -> int:
    """Heavy merge pass — run at most once every few minutes, not on every inbox poll."""
    global _CONSOLIDATE_LAST_AT
    now = time.monotonic()
    if now - _CONSOLIDATE_LAST_AT < _CONSOLIDATE_COOLDOWN_SEC:
        return 0
    _CONSOLIDATE_LAST_AT = now
    return consolidate_junk_whatsapp_leads(db)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def normalize_wa_phone(value: str) -> str:
    raw = str(value or "").strip()
    if "@" in raw:
        host = raw.split("@", 1)[1].split("_")[0].split(":")[0].lower()
        if host == "lid":
            return ""
        raw = raw.split("@", 1)[0]
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"+91{digits}"
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    return ""


def _normalize_wa_chat_id(chat_id: str) -> str:
    """Canonical WhatsApp chat id (LID internals always use @lid, never @c.us)."""
    text = str(chat_id or "").strip()
    if not text:
        return ""
    match = re.search(r"(\d{8,16})@(lid|c\.us)", text)
    if not match:
        digits = re.sub(r"\D", "", text)
        if len(digits) > 12:
            return f"{digits}@lid"
        if len(digits) >= 10:
            return f"{digits}@c.us"
        return ""
    digits, suffix = match.group(1), match.group(2)
    if len(digits) > 12 or suffix == "lid":
        return f"{digits}@lid"
    if len(digits) == 10:
        return f"91{digits}@c.us"
    return f"{digits}@c.us"


def _chat_id_match_keys(chat_id: str) -> set[str]:
    cid = _normalize_wa_chat_id(chat_id)
    if not cid:
        return set()
    digits = cid.split("@", 1)[0]
    keys = {cid, f"{digits}@lid", f"{digits}@c.us"}
    if len(digits) == 12 and digits.startswith("91"):
        keys.add(f"{digits[2:]}@c.us")
    return {k for k in keys if k}


def _extract_wa_chat_id(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("wa-chat:"):
        text = text.split(":", 1)[-1]
    return _normalize_wa_chat_id(text)


def _junk_wa_phone_label(phone: str) -> bool:
    norm = normalize_wa_phone(phone)
    if norm:
        return False
    digits = re.sub(r"\D", "", str(phone or ""))
    return len(digits) > 12


def _thread_display_name(lead: InstituteLead) -> str:
    name = (lead.display_name or "").strip()
    if name and not _junk_wa_phone_label(name) and not name.startswith("+"):
        return name[:190]
    if name and not _junk_wa_phone_label(name):
        return name[:190]
    norm = normalize_wa_phone(lead.whatsapp_phone or "")
    if norm:
        return name if name and not _junk_wa_phone_label(name) else norm
    return name if name and not _junk_wa_phone_label(name) else "WhatsApp contact"


def _looks_like_unresolved_lid_phone(phone: str, chat_id: str = "") -> bool:
    digits = re.sub(r"\D", "", str(phone or ""))
    cid = str(chat_id or "")
    return cid.endswith("@lid") and len(digits) > 13


def _phone_keys(phone: str) -> set[str]:
    norm = normalize_wa_phone(phone)
    digits = re.sub(r"\D", "", norm)
    keys = {norm, digits}
    if len(digits) == 12 and digits.startswith("91"):
        keys.add(digits[2:])
        keys.add(f"+{digits}")
    if len(digits) == 10:
        keys.add(f"91{digits}")
        keys.add(f"+91{digits}")
    return {k for k in keys if k}


def find_lead_by_whatsapp_chat_id(db: Session, chat_id: str) -> InstituteLead | None:
    keys = _chat_id_match_keys(chat_id)
    if not keys:
        return None
    digits = next((k.split("@", 1)[0] for k in keys if "@" in k), "")
    matches: list[InstituteLead] = []
    for lead in db.scalars(select(InstituteLead).options(joinedload(InstituteLead.profile))).unique().all():
        stored = _lead_whatsapp_chat_id(lead)
        if stored and _chat_id_match_keys(stored) & keys:
            matches.append(lead)
            continue
        if digits and (lead.dedupe_key or "").startswith("wa-chat:") and digits in lead.dedupe_key:
            matches.append(lead)
    if not matches:
        return None
    real = [lead for lead in matches if not _is_ephemeral_wa_chat_lead(lead)]
    if real:
        return max(real, key=lambda row: row.completeness_score)
    return matches[0]


def _find_lead_for_lid_chat_id(db: Session, chat_id: str, *, message_limit: int = 200) -> InstituteLead | None:
    keys = _chat_id_match_keys(chat_id)
    for lead in db.scalars(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile))
        .where(InstituteLead.whatsapp_phone != "")
        .order_by(InstituteLead.completeness_score.desc())
    ).unique().all():
        if not normalize_wa_phone(lead.whatsapp_phone or ""):
            continue
        if (lead.dedupe_key or "").startswith("manual:") and keys & _chat_id_match_keys(_lead_whatsapp_chat_id(lead)):
            return lead
    try:
        hist = whatsapp_bridge_client.fetch_chat_messages(_normalize_wa_chat_id(chat_id), limit=message_limit)
    except Exception:
        return None
    needles: list[str] = []
    brand_hit = False
    for msg in hist.get("items") or []:
        if not isinstance(msg, dict) or not msg.get("from_me"):
            continue
        body = str(msg.get("body") or "").strip()
        if "ApplyXAI" in body:
            brand_hit = True
            needles.append(body[:240])
        elif len(body) >= 24:
            needles.append(body[:240])
    needles = needles[-8:]
    if not needles and not brand_hit:
        return None
    rows = db.scalars(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile))
        .where(InstituteLead.whatsapp_phone != "")
        .order_by(InstituteLead.completeness_score.desc())
    ).unique().all()
    for candidate in rows:
        if not normalize_wa_phone(candidate.whatsapp_phone or ""):
            continue
        if brand_hit:
            branded = db.scalar(
                select(InstituteLeadChatMessage.id)
                .where(
                    InstituteLeadChatMessage.lead_id == candidate.id,
                    InstituteLeadChatMessage.direction == "outbound",
                    InstituteLeadChatMessage.body.ilike("%ApplyXAI%"),
                )
                .limit(1)
            )
            if branded is not None:
                _remember_lead_whatsapp_chat_id(db, candidate, chat_id)
                return candidate
        outbound = db.scalars(
            select(InstituteLeadChatMessage.body)
            .where(
                InstituteLeadChatMessage.lead_id == candidate.id,
                InstituteLeadChatMessage.direction == "outbound",
            )
            .limit(12)
        ).all()
        for body in outbound:
            text = str(body or "").strip()
            for needle in needles:
                if needle in text or text in needle:
                    _remember_lead_whatsapp_chat_id(db, candidate, chat_id)
                    return candidate
    return None


def _is_ephemeral_wa_chat_lead(lead: InstituteLead) -> bool:
    return (lead.dedupe_key or "").startswith("wa-chat:") and not normalize_wa_phone(lead.whatsapp_phone or "")


def _resolve_institute_lead_for_chat(db: Session, chat_id: str) -> InstituteLead | None:
    cid = _normalize_wa_chat_id(chat_id)
    if not cid:
        return None
    stored = find_lead_by_whatsapp_chat_id(db, cid)
    if stored is not None and not _is_ephemeral_wa_chat_lead(stored):
        if (stored.dedupe_key or "").startswith("manual:") or stored.completeness_score >= 40:
            return stored
    real = _find_lead_for_lid_chat_id(db, cid)
    if real is not None:
        return real
    if stored is not None and not _is_ephemeral_wa_chat_lead(stored):
        return stored
    return None


def resolve_lead_for_whatsapp_inbound(
    db: Session,
    *,
    from_wa: str,
    display_name: str = "",
    message_id: str | None = None,
    chat_id: str = "",
) -> InstituteLead:
    chat_id = _normalize_wa_chat_id(
        (chat_id or "").strip() or _extract_wa_chat_id(from_wa) or _extract_wa_chat_id(message_id or "")
    )
    if normalize_wa_phone(from_wa):
        lead = find_lead_by_phone(db, from_wa)
        if lead is not None:
            if chat_id:
                _remember_lead_whatsapp_chat_id(db, lead, chat_id)
            if display_name and not (lead.display_name or "").strip():
                lead.display_name = display_name[:190]
            return lead
    if chat_id:
        lead = _resolve_institute_lead_for_chat(db, chat_id)
        if lead is not None:
            if display_name and _should_use_inbound_display_name(lead, display_name):
                lead.display_name = display_name[:190]
            _remember_lead_whatsapp_chat_id(db, lead, chat_id)
            return lead
    return get_or_create_lead_for_whatsapp(db, from_wa, display_name=display_name, chat_id=chat_id)


def _should_use_inbound_display_name(lead: InstituteLead, display_name: str) -> bool:
    name = (display_name or "").strip()
    if not name or name.lower() in {"no name", "whatsapp contact"}:
        return False
    existing = (lead.display_name or "").strip()
    if not existing:
        return True
    if existing.lower() in {"no name", "whatsapp contact"}:
        return True
    if lead.dedupe_key.startswith("manual:") or lead.completeness_score >= 40:
        return False
    return not existing


def get_or_create_lead_for_whatsapp(
    db: Session,
    phone: str,
    *,
    display_name: str = "",
    chat_id: str = "",
) -> InstituteLead:
    chat_id = _normalize_wa_chat_id((chat_id or "").strip() or _extract_wa_chat_id(phone))
    if chat_id:
        lead = find_lead_by_whatsapp_chat_id(db, chat_id)
        if lead is None:
            lead = _find_lead_for_lid_chat_id(db, chat_id)
        if lead is not None:
            if display_name and not (lead.display_name or "").strip():
                lead.display_name = display_name[:190]
            _remember_lead_whatsapp_chat_id(db, lead, chat_id)
            return lead

    lead = find_lead_by_phone(db, phone)
    if lead is not None:
        norm = normalize_wa_phone(phone)
        if norm and not lead.whatsapp_phone:
            lead.whatsapp_phone = norm[:32]
        if display_name and not (lead.display_name or "").strip():
            lead.display_name = display_name[:190]
        if chat_id:
            _remember_lead_whatsapp_chat_id(db, lead, chat_id)
        return lead
    norm = normalize_wa_phone(phone)
    if not norm:
        if chat_id:
            lead = _find_lead_for_lid_chat_id(db, chat_id)
            if lead is not None:
                _remember_lead_whatsapp_chat_id(db, lead, chat_id)
                return lead
        name = (display_name or "WhatsApp contact").strip()[:190]
        if name.lower() == "no name":
            name = "WhatsApp contact"
        dedupe = f"wa-chat:{chat_id}" if chat_id else f"wa:{uuid.uuid4()}"
        existing = db.scalar(select(InstituteLead).where(InstituteLead.dedupe_key == dedupe))
        if existing is not None:
            if chat_id:
                _remember_lead_whatsapp_chat_id(db, existing, chat_id)
            return existing
        lead = InstituteLead(
            dedupe_key=dedupe,
            display_name=name,
            status="replied",
            whatsapp_phone="",
            source_platform="whatsapp",
        )
        db.add(lead)
        db.flush()
        if chat_id:
            _remember_lead_whatsapp_chat_id(db, lead, chat_id)
        return lead
    digits = re.sub(r"\D", "", norm)
    dedupe = f"wa:{digits}" if digits else f"wa:{uuid.uuid4()}"
    existing = db.scalar(select(InstituteLead).where(InstituteLead.dedupe_key == dedupe))
    if existing is not None:
        if norm and not existing.whatsapp_phone:
            existing.whatsapp_phone = norm[:32]
        return existing
    name = (display_name or norm or "WhatsApp contact").strip()[:190]
    lead = InstituteLead(
        dedupe_key=dedupe,
        display_name=name,
        status="replied",
        whatsapp_phone=(norm or "")[:32],
        source_platform="whatsapp",
    )
    db.add(lead)
    db.flush()
    return lead


def _wa_ts_to_dt(ts: int | float | None) -> datetime:
    if ts is None:
        return _now()
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return _now()


def _import_bridge_message(db: Session, lead: InstituteLead, msg: dict) -> bool:
    body = str(msg.get("body") or "").strip()
    if not body:
        return False
    ext = str(msg.get("id") or "").strip() or f"wa:{uuid.uuid4()}"
    ext = ext[:190]
    existing = db.scalar(select(InstituteLeadChatMessage.id).where(InstituteLeadChatMessage.external_id == ext))
    if existing is not None:
        return False
    when = _wa_ts_to_dt(msg.get("timestamp"))
    direction = "outbound" if msg.get("from_me") else "inbound"
    row = InstituteLeadChatMessage(
        lead_id=lead.id,
        channel="whatsapp",
        direction=direction,
        body=body[:8000],
        external_id=ext,
        created_at=when,
        updated_at=when,
    )
    db.add(row)
    if direction == "inbound" and lead.status == "sent":
        lead.status = "replied"
    db.flush()
    return True


def _humanize_wa_bridge_error(msg: str) -> str:
    text = (msg or "").strip()
    if not text:
        return "Could not reach WhatsApp bridge."
    if "detached Frame" in text or "stale_session" in text.lower():
        return (
            "WhatsApp Web lost its browser session (detached frame). "
            "Restart .\\scripts\\start_whatsapp_bridge.ps1, wait until Connected, then click Load from WhatsApp again."
        )
    if "Could not list chats:" in text:
        return _humanize_wa_bridge_error(text.split("Could not list chats:", 1)[-1].strip())
    return text


def sync_chats_from_bridge(db: Session, *, chat_limit: int = 150, message_limit: int = 80) -> dict:
    """Pull WhatsApp Web conversations into institute lead chat threads."""
    remote = whatsapp_bridge_client.get_status()
    if remote.get("status") != "connected" or not remote.get("ready"):
        err = str(remote.get("error") or "")
        if "already running" in err.lower():
            whatsapp_bridge_client.reset_client()
            return {
                "synced": False,
                "reason": (
                    "WhatsApp bridge is reconnecting after a stale browser session. "
                    "Wait ~10 seconds, open Outreach → WhatsApp, then try Load from WhatsApp again."
                ),
                "chats": 0,
                "messages_imported": 0,
            }
        if err.strip():
            return {
                "synced": False,
                "reason": _humanize_wa_bridge_error(err),
                "chats": 0,
                "messages_imported": 0,
            }
        return {"synced": False, "reason": "not_connected", "chats": 0, "messages_imported": 0}

    payload = whatsapp_bridge_client.list_chats(limit=chat_limit)
    if not payload.get("ok", True) and not payload.get("items"):
        err = payload.get("error") or "bridge_error"
        if "detached Frame" in err or payload.get("stale_session"):
            whatsapp_bridge_client.reset_client()
        return {
            "synced": False,
            "reason": _humanize_wa_bridge_error(str(err)),
            "chats": 0,
            "messages_imported": 0,
        }

    chats = payload.get("items") or []
    imported = 0
    leads_touched = 0
    for chat in chats:
        chat_id = str(chat.get("id") or "").strip()
        phone = str(chat.get("phone") or "").strip()
        if not phone and chat_id:
            phone = chat_id.split("@", 1)[0]
        if not phone:
            continue
        if _looks_like_unresolved_lid_phone(phone, chat_id) and not chat.get("phone_resolved"):
            continue
        name = str(chat.get("name") or "").strip()
        lead = find_lead_by_phone(db, phone)
        if lead is None:
            lead = get_or_create_lead_for_whatsapp(db, phone, display_name=name)
        elif name and not (lead.display_name or "").strip():
            lead.display_name = name[:190]
        leads_touched += 1

        last = chat.get("last_message")
        if isinstance(last, dict) and last.get("body"):
            if _import_bridge_message(db, lead, last):
                imported += 1

        if chat_id:
            imported += _import_chat_history(db, lead, chat_id, phone=phone, message_limit=message_limit)

    return {
        "synced": True,
        "chats": len(chats),
        "leads_touched": leads_touched,
        "messages_imported": imported,
        "bridge_total": int(payload.get("total") or len(chats)),
        "leads_merged": consolidate_junk_whatsapp_leads(db),
    }


def find_lead_by_phone(db: Session, phone: str) -> InstituteLead | None:
    keys = _phone_keys(phone)
    if not keys:
        return None
    leads = db.scalars(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile))
        .where(InstituteLead.whatsapp_phone != "")
    ).unique().all()
    for lead in leads:
        if _phone_keys(lead.whatsapp_phone) & keys:
            return lead
    for lead in db.scalars(select(InstituteLead).options(joinedload(InstituteLead.profile))).unique().all():
        profile = lead.profile.payload if lead.profile else {}
        for p in profile.get("phones") or []:
            if _phone_keys(str(p)) & keys:
                return lead
    return None


def chat_message_out(row: InstituteLeadChatMessage) -> dict:
    return {
        "id": str(row.id),
        "channel": row.channel,
        "direction": row.direction,
        "body": row.body,
        "created_at": _iso(row.created_at),
    }


def list_chat_threads(
    db: Session,
    params: PageParams,
    *,
    q: str | None = None,
) -> dict:
    _maybe_consolidate_junk_leads(db)
    agg = select(
        InstituteLeadChatMessage.lead_id.label("lead_id"),
        func.max(InstituteLeadChatMessage.created_at).label("last_at"),
    ).group_by(InstituteLeadChatMessage.lead_id)
    if q:
        like = f"%{q.strip()}%"
        agg = agg.join(InstituteLead, InstituteLead.id == InstituteLeadChatMessage.lead_id).where(
            (InstituteLead.display_name.ilike(like)) | (InstituteLead.whatsapp_phone.ilike(like))
        )
    agg_sub = agg.subquery()
    total = db.scalar(select(func.count()).select_from(agg_sub)) or 0
    lead_rows = db.execute(
        select(agg_sub.c.lead_id, agg_sub.c.last_at)
        .order_by(agg_sub.c.last_at.desc())
        .limit(params.page_size)
        .offset((params.page - 1) * params.page_size)
    ).all()
    items: list[dict] = []
    for lead_id, _last_at in lead_rows:
        lead = db.get(InstituteLead, lead_id)
        if lead is None:
            continue
        last_msg = db.scalar(
            select(InstituteLeadChatMessage)
            .where(InstituteLeadChatMessage.lead_id == lead_id)
            .order_by(
                InstituteLeadChatMessage.created_at.desc(),
                InstituteLeadChatMessage.updated_at.desc(),
                InstituteLeadChatMessage.external_id.desc(),
            )
            .limit(1)
        )
        if last_msg is None:
            continue
        count = db.scalar(
            select(func.count())
            .select_from(InstituteLeadChatMessage)
            .where(InstituteLeadChatMessage.lead_id == lead.id)
        )
        phone_out = normalize_wa_phone(lead.whatsapp_phone or "") or (
            "" if _junk_wa_phone_label(lead.whatsapp_phone or "") else (lead.whatsapp_phone or "")
        )
        items.append(
            {
                "lead_id": str(lead.id),
                "display_name": _thread_display_name(lead),
                "status": lead.status,
                "whatsapp_phone": phone_out,
                "message_count": int(count or 0),
                "last_message": chat_message_out(last_msg),
            }
        )
    return page_response(items, total, params)


def _signature_outbound_body(db: Session, lead_id: uuid.UUID) -> str:
    rows = db.scalars(
        select(InstituteLeadChatMessage.body)
        .where(
            InstituteLeadChatMessage.lead_id == lead_id,
            InstituteLeadChatMessage.direction == "outbound",
        )
        .order_by(InstituteLeadChatMessage.created_at.desc())
        .limit(40)
    ).all()
    best = ""
    for body in rows:
        text = str(body or "").strip()
        if len(text) < 24 or len(text) > 2000:
            continue
        if text.startswith("/9j/") or text.startswith("[") or text.endswith(".apk"):
            continue
        if "ApplyXAI" in text or "institute" in text.lower():
            return text
        if len(text) > len(best):
            best = text
    return best


def _find_merge_target_for_ghost(db: Session, ghost: InstituteLead, chat_id: str) -> InstituteLead | None:
    if chat_id:
        target = _resolve_institute_lead_for_chat(db, chat_id)
        if target is not None and target.id != ghost.id:
            return target
        target = _find_lead_for_lid_chat_id(db, chat_id)
        if target is not None and target.id != ghost.id:
            return target
    text = _signature_outbound_body(db, ghost.id)
    if len(text) >= 24:
        other_id = db.scalar(
            select(InstituteLeadChatMessage.lead_id)
            .join(InstituteLead, InstituteLead.id == InstituteLeadChatMessage.lead_id)
            .where(
                InstituteLeadChatMessage.body == text,
                InstituteLeadChatMessage.lead_id != ghost.id,
                InstituteLead.whatsapp_phone != "",
            )
            .limit(1)
        )
        if other_id is not None:
            other = db.get(InstituteLead, other_id)
            if other is not None and normalize_wa_phone(other.whatsapp_phone or ""):
                if chat_id:
                    _remember_lead_whatsapp_chat_id(db, other, chat_id)
                return other
    return None


def consolidate_junk_whatsapp_leads(db: Session) -> int:
    """Merge chat threads that were keyed on WhatsApp LID ids into real institute leads."""
    junk: list[InstituteLead] = []
    for lead in db.scalars(select(InstituteLead).options(joinedload(InstituteLead.profile))).unique().all():
        phone = (lead.whatsapp_phone or "").strip()
        name = (lead.display_name or "").strip()
        if _junk_wa_phone_label(phone) or _junk_wa_phone_label(name):
            junk.append(lead)
            continue
        if (lead.dedupe_key or "").startswith("wa-chat:") and not normalize_wa_phone(phone):
            junk.append(lead)
            continue
        if (lead.dedupe_key or "").startswith("wa:") and not normalize_wa_phone(phone):
            digits = re.sub(r"\D", "", lead.dedupe_key.split(":", 1)[-1])
            if len(digits) > 12:
                junk.append(lead)
    merged = 0
    for ghost in junk:
        chat_id = _normalize_wa_chat_id(
            _lead_whatsapp_chat_id(ghost)
            or _extract_wa_chat_id(ghost.dedupe_key or "")
            or _extract_wa_chat_id(ghost.whatsapp_phone or ghost.display_name or "")
        )
        target = _find_merge_target_for_ghost(db, ghost, chat_id)
        if target is None or target.id == ghost.id:
            continue
        if chat_id:
            _remember_lead_whatsapp_chat_id(db, target, chat_id)
        target_ids = set(
            db.scalars(
                select(InstituteLeadChatMessage.external_id).where(
                    InstituteLeadChatMessage.lead_id == target.id
                )
            ).all()
        )
        ghost_msgs = db.scalars(
            select(InstituteLeadChatMessage).where(InstituteLeadChatMessage.lead_id == ghost.id)
        ).all()
        move_ids: list[uuid.UUID] = []
        drop_ids: list[uuid.UUID] = []
        for msg in ghost_msgs:
            if msg.external_id in target_ids:
                drop_ids.append(msg.id)
            else:
                move_ids.append(msg.id)
                target_ids.add(msg.external_id)
        if move_ids:
            db.execute(
                update(InstituteLeadChatMessage)
                .where(InstituteLeadChatMessage.id.in_(move_ids))
                .values(lead_id=target.id)
            )
        if drop_ids:
            db.execute(delete(InstituteLeadChatMessage).where(InstituteLeadChatMessage.id.in_(drop_ids)))
        if ghost.status == "replied" and target.status == "sent":
            target.status = "replied"
        db.execute(delete(InstituteLeadChatMessage).where(InstituteLeadChatMessage.lead_id == ghost.id))
        db.delete(ghost)
        merged += 1
        db.flush()
    return merged


def _lead_whatsapp_chat_id(lead: InstituteLead) -> str:
    profile = lead.profile.payload if lead.profile else {}
    return str(profile.get("whatsapp_chat_id") or "").strip()


def _remember_lead_whatsapp_chat_id(db: Session, lead: InstituteLead, chat_id: str) -> None:
    cid = _normalize_wa_chat_id(chat_id or "")
    if not cid or not lead.profile:
        return
    payload = dict(lead.profile.payload or {})
    if payload.get("whatsapp_chat_id") == cid:
        return
    payload["whatsapp_chat_id"] = cid
    lead.profile.payload = payload
    db.flush()


def _outbound_match_needles(db: Session, lead: InstituteLead) -> list[str]:
    rows = db.scalars(
        select(InstituteLeadChatMessage.body)
        .where(
            InstituteLeadChatMessage.lead_id == lead.id,
            InstituteLeadChatMessage.direction == "outbound",
        )
        .order_by(InstituteLeadChatMessage.created_at.desc())
        .limit(8)
    ).all()
    needles: list[str] = []
    for body in rows:
        text = str(body or "").strip()
        if len(text) < 24:
            continue
        needles.append(text[:240])
        if len(needles) >= 4:
            break
    return needles


def _chat_ids_by_outbound_fingerprint(db: Session, lead: InstituteLead, *, list_limit: int = 120) -> list[str]:
    """Match WhatsApp @lid threads by comparing stored outbound text to bridge history."""
    needles = _outbound_match_needles(db, lead)
    if not needles:
        return []
    payload = whatsapp_bridge_client.list_chats(limit=list_limit)
    matched: list[str] = []
    for chat in payload.get("items") or []:
        if not isinstance(chat, dict):
            continue
        chat_id = str(chat.get("id") or "").strip()
        if not chat_id:
            continue
        try:
            hist = whatsapp_bridge_client.fetch_chat_messages(chat_id, limit=40)
        except Exception:
            logger.debug("fingerprint fetch failed for %s", chat_id, exc_info=True)
            continue
        for msg in hist.get("items") or []:
            if not isinstance(msg, dict) or not msg.get("from_me"):
                continue
            body = str(msg.get("body") or "").strip()
            if not body:
                continue
            for needle in needles:
                if needle in body or body in needle:
                    matched.append(chat_id)
                    _remember_lead_whatsapp_chat_id(db, lead, chat_id)
                    break
            if chat_id in matched:
                break
        if len(matched) >= 2:
            break
    return matched


def _chat_ids_for_lead(db: Session, lead: InstituteLead, phone: str, *, list_limit: int = 200) -> list[str]:
    ids: list[str] = []
    stored = _lead_whatsapp_chat_id(lead)
    if stored:
        ids.append(stored)
    for cid in _chat_ids_for_phone(phone, list_limit=list_limit):
        if cid not in ids:
            ids.append(cid)
    digits = re.sub(r"\D", "", normalize_wa_phone(phone))
    only_default = ids == [f"{digits}@c.us"] if digits else len(ids) <= 1
    if only_default:
        for cid in _chat_ids_by_outbound_fingerprint(db, lead, list_limit=min(list_limit, 120)):
            if cid not in ids:
                ids.append(cid)
    return ids


def _chat_ids_for_phone(phone: str, *, list_limit: int = 200) -> list[str]:
    digits = re.sub(r"\D", "", normalize_wa_phone(phone))
    if not digits:
        return []
    ids: list[str] = [f"{digits}@c.us"]
    keys = _phone_keys(phone)
    payload = whatsapp_bridge_client.list_chats(limit=list_limit)
    for chat in payload.get("items") or []:
        if not isinstance(chat, dict):
            continue
        chat_phone = str(chat.get("phone") or "")
        chat_id = str(chat.get("id") or "").strip()
        if not chat_id:
            continue
        if chat_phone and _phone_keys(chat_phone) & keys:
            if chat_id not in ids:
                ids.append(chat_id)
    return ids


def _import_chat_history(
    db: Session,
    lead: InstituteLead,
    chat_id: str,
    *,
    phone: str = "",
    message_limit: int = 100,
) -> int:
    imported = 0
    hist = whatsapp_bridge_client.fetch_chat_messages(chat_id, limit=message_limit)
    for msg in hist.get("items") or []:
        if isinstance(msg, dict) and _import_bridge_message(db, lead, msg):
            imported += 1
    if imported == 0 and phone:
        for alt_id in _chat_ids_for_phone(phone):
            if alt_id == chat_id:
                continue
            hist = whatsapp_bridge_client.fetch_chat_messages(alt_id, limit=message_limit)
            for msg in hist.get("items") or []:
                if isinstance(msg, dict) and _import_bridge_message(db, lead, msg):
                    imported += 1
            if imported:
                break
    return imported


def sync_lead_chat_from_bridge(db: Session, lead: InstituteLead, *, message_limit: int = 150) -> int:
    """Fetch WhatsApp history for one lead from the bridge."""
    remote = whatsapp_bridge_client.get_status()
    if remote.get("status") != "connected" or not remote.get("ready"):
        return 0
    phone = (lead.whatsapp_phone or "").strip()
    if not phone:
        profile = lead.profile.payload if lead.profile else {}
        phones = profile.get("phones") or []
        phone = normalize_wa_phone(str(phones[0])) if phones else ""
    if not phone:
        return 0
    imported = 0
    for chat_id in _chat_ids_for_lead(db, lead, phone):
        n = _import_chat_history(db, lead, chat_id, phone=phone, message_limit=message_limit)
        imported += n
        if n and chat_id:
            _remember_lead_whatsapp_chat_id(db, lead, chat_id)
    return imported


def list_chat(db: Session, lead: InstituteLead, *, sync_bridge: bool = True) -> list[dict]:
    if sync_bridge:
        remote = whatsapp_bridge_client.get_status()
        bridge_up = remote.get("status") == "connected" and remote.get("ready")
        now = time.monotonic()
        last = _CHAT_BRIDGE_SYNC_AT.get(lead.id, 0.0)
        if bridge_up and now - last >= _CHAT_SYNC_COOLDOWN_SEC:
            _CHAT_BRIDGE_SYNC_AT[lead.id] = now
            try:
                sync_lead_chat_from_bridge(db, lead)
            except Exception:
                logger.exception("Lead chat sync failed for %s", lead.id)
    rows = db.scalars(
        select(InstituteLeadChatMessage)
        .where(InstituteLeadChatMessage.lead_id == lead.id)
        .order_by(InstituteLeadChatMessage.created_at.asc())
    ).all()
    return [chat_message_out(r) for r in rows]


def record_outbound(
    db: Session,
    lead: InstituteLead,
    *,
    body: str,
    channel: str = "whatsapp",
    external_id: str | None = None,
) -> InstituteLeadChatMessage:
    ext = (external_id or "").strip() or f"out:{uuid.uuid4()}"
    row = InstituteLeadChatMessage(
        lead_id=lead.id,
        channel=channel,
        direction="outbound",
        body=body.strip(),
        external_id=ext[:190],
    )
    db.add(row)
    db.flush()
    return row


def ingest_inbound(
    db: Session,
    *,
    from_wa: str,
    body: str,
    message_id: str | None = None,
    display_name: str = "",
    chat_id: str = "",
) -> dict | None:
    text = (body or "").strip()
    if not text:
        return None
    ext = (message_id or "").strip() or f"in:{uuid.uuid4()}"
    if len(ext) > 190:
        ext = ext[:190]
    existing = db.scalar(select(InstituteLeadChatMessage.id).where(InstituteLeadChatMessage.external_id == ext))
    if existing is not None:
        return None

    lead = resolve_lead_for_whatsapp_inbound(
        db,
        from_wa=from_wa,
        display_name=display_name.strip(),
        message_id=message_id,
        chat_id=chat_id,
    )
    consolidate_junk_whatsapp_leads(db)

    phone = normalize_wa_phone(from_wa)
    if phone and not lead.whatsapp_phone:
        lead.whatsapp_phone = phone[:32]
    if lead.status == "sent":
        lead.status = "replied"

    row = InstituteLeadChatMessage(
        lead_id=lead.id,
        channel="whatsapp",
        direction="inbound",
        body=text[:8000],
        external_id=ext,
    )
    db.add(row)
    db.flush()
    from backend.app.services import institute_outreach_bot_service

    institute_outreach_bot_service.maybe_auto_reply(db, lead, text)
    return {"lead_id": str(lead.id), "message": chat_message_out(row)}


def _whatsapp_provider(db: Session) -> str:
    from backend.app.services.platform_settings_service import get_outreach_admin
    return str(get_outreach_admin(db).get("whatsapp_provider") or "bridge")


def send_whatsapp_reply(
    db: Session,
    lead: InstituteLead,
    text: str,
    *,
    attachment_path: str | None = None,
    attachment_name: str = "",
) -> dict:
    if _whatsapp_provider(db) == "cloud":
        from backend.app.services import whatsapp_cloud_client
        phone = (lead.whatsapp_phone or "").strip()
        if not phone:
            profile = lead.profile.payload if lead.profile else {}
            phones = profile.get("phones") or []
            phone = str(phones[0]) if phones else ""
        if not phone:
            raise AppError("NO_PHONE", "Lead has no WhatsApp phone number.", 422)
        cleaned = text.strip()
        media = (attachment_path or "").strip()
        fname = (attachment_name or "").strip()
        if not cleaned and not media:
            raise AppError("VALIDATION_ERROR", "Message text or an attachment is required.", 422)
        if media:
            result = whatsapp_cloud_client.send_media(
                phone, media, caption=cleaned or fname or "Attachment", filename=fname,
            )
            stored_body = cleaned or fname or "Attachment"
            if cleaned and fname:
                stored_body = f"{cleaned}\n[attachment: {fname}]"
            elif fname:
                stored_body = f"[attachment: {fname}]"
        else:
            result = whatsapp_cloud_client.send_text(phone, cleaned)
            stored_body = cleaned
        lead.whatsapp_phone = phone[:32]
        ext = str(result.get("id") or "")
        row = record_outbound(db, lead, body=stored_body[:8000], external_id=f"cloud:{ext or uuid.uuid4()}")
        return {"message": chat_message_out(row), "cloud": result, "channel": "whatsapp"}

    remote = whatsapp_bridge_client.get_status()
    if remote.get("status") != "connected" or not remote.get("ready"):
        detail = (remote.get("error") or "").strip()
        message = "WhatsApp is not connected."
        if detail:
            message = f"{message} {detail}"
        elif remote.get("status") == "qr":
            message = "WhatsApp is waiting for QR scan. Open Admin → Outreach → WhatsApp and link your phone."
        else:
            message = (
                f"{message} Start the bridge with .\\scripts\\start_whatsapp_bridge.ps1, "
                "then scan the QR code under Admin → Outreach → WhatsApp."
            )
        raise AppError("WHATSAPP_NOT_READY", message[:2000], 503)

    phone = (lead.whatsapp_phone or "").strip()
    if not phone:
        profile = lead.profile.payload if lead.profile else {}
        phones = profile.get("phones") or []
        phone = normalize_wa_phone(str(phones[0])) if phones else ""
    if not phone:
        raise AppError("NO_PHONE", "Lead has no WhatsApp phone number.", 422)

    cleaned = text.strip()
    media = (attachment_path or "").strip()
    fname = (attachment_name or "").strip()
    if not cleaned and not media:
        raise AppError("VALIDATION_ERROR", "Message text or an attachment is required.", 422)
    caption = cleaned or fname or "Attachment"
    if media:
        result = whatsapp_bridge_client.send_message(
            phone,
            caption,
            media_path=media,
            caption=caption,
        )
        stored_body = caption if cleaned else f"[attachment: {fname or 'file'}]"
        if cleaned and fname:
            stored_body = f"{caption}\n[attachment: {fname}]"
    else:
        result = whatsapp_bridge_client.send_message(phone, cleaned)
        stored_body = cleaned
    lead.whatsapp_phone = phone[:32]
    row = record_outbound(db, lead, body=stored_body[:8000], external_id=f"out:{uuid.uuid4()}")
    return {"message": chat_message_out(row), "bridge": result}


def verify_bridge_secret(provided: str) -> None:
    secret = (settings.WHATSAPP_BRIDGE_SECRET or "").strip()
    if not secret:
        raise AppError("BRIDGE_SECRET_NOT_SET", "Set WHATSAPP_BRIDGE_SECRET in .env for inbound WhatsApp.", 503)
    if provided != secret:
        raise AppError("UNAUTHORIZED", "Invalid bridge secret.", 401)
