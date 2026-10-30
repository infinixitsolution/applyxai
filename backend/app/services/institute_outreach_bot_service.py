"""AI auto-replies for institute outreach WhatsApp threads after initial send."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.app.models.outreach import InstituteLead
from backend.app.services import ai_service, whatsapp_bridge_client
from backend.app.services.ai_service import AiTask
from backend.app.services.institute_outreach_chat_service import normalize_wa_phone, record_outbound

logger = logging.getLogger("applyxai.outreach.bot")


def outreach_chatbot_enabled(lead: InstituteLead) -> bool:
    profile = lead.profile.payload if lead.profile else {}
    return bool(profile.get("outreach_chatbot_enabled"))


def enable_outreach_chatbot(db: Session, lead: InstituteLead) -> None:
    if lead.profile is None:
        return
    payload = dict(lead.profile.payload or {})
    if payload.get("outreach_chatbot_enabled"):
        return
    payload["outreach_chatbot_enabled"] = True
    lead.profile.payload = payload
    db.flush()


def maybe_auto_reply(db: Session, lead: InstituteLead, inbound_text: str) -> bool:
    if not outreach_chatbot_enabled(lead):
        return False
    text = (inbound_text or "").strip()
    if len(text) < 2:
        return False
    remote = whatsapp_bridge_client.get_status()
    if remote.get("status") != "connected" or not remote.get("ready"):
        return False
    phone = (lead.whatsapp_phone or "").strip()
    if not phone and lead.profile:
        phones = lead.profile.payload.get("phones") or []
        phone = normalize_wa_phone(str(phones[0])) if phones else ""
    if not phone:
        return False
    institute = (lead.display_name or "your institute").strip()
    try:
        reply = ai_service.complete(
            db,
            AiTask.APP_ANSWER,
            system=(
                "You are ApplyXAI partnership outreach assistant. Reply on WhatsApp to an institute contact. "
                "Be warm, concise (under 120 words), professional. Mention campus partnership, student job readiness, "
                "and institute registration when relevant. Plain text only, no markdown."
            ),
            user=f"Institute: {institute}\nTheir message: {text}\n\nDraft a helpful reply.",
            feature="outreach",
            max_tokens=350,
        )
    except Exception:
        logger.exception("Outreach auto-reply AI failed for lead %s", lead.id)
        return False
    cleaned = (reply or "").strip()
    if len(cleaned) < 8:
        return False
    try:
        whatsapp_bridge_client.send_message(phone, cleaned)
        record_outbound(db, lead, body=cleaned)
        return True
    except Exception:
        logger.exception("Outreach auto-reply send failed for lead %s", lead.id)
        return False
