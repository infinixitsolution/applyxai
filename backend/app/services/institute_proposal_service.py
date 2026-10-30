"""Generate email and WhatsApp proposal copy for institute leads."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import PROJECT_ROOT, settings
from backend.app.services import ai_service, platform_settings_service as ps
from backend.app.services.ai_service import AiTask
from backend.app.services.email_service import text_to_html

logger = logging.getLogger("applyxai.outreach.proposal")

DEFAULT_WHATSAPP_BODY = (
    "Hi {contact_name} 👋\n\n"
    "I'm reaching out from ApplyXAI.\n\n"
    "We partner with institutes like {institute_name} to help students become more job-ready through "
    "AI-powered job applications, interview preparation, and career support.\n\n"
    "With ApplyXAI, your students can get support with:\n"
    "• AI-assisted job applications\n"
    "• Resume and profile optimization\n"
    "• Interview preparation & coaching\n"
    "• Application and career progress tracking\n\n"
    "We'd love to explore a Campus Partnership with {institute_name} and show you how ApplyXAI can support "
    "your students' placement journey.\n\n"
    "Interested in learning more?\n\n"
    "👉 Create your Institute Account: {link}\n\n"
    "It only takes a few minutes to get started.\n\n"
    "— Team ApplyXAI"
)

DEFAULT_EMAIL_BODY = (
    "Hi {contact_name},\n\n"
    "I'm reaching out from ApplyXAI.\n\n"
    "We partner with institutes like {institute_name} to help students become more job-ready through "
    "AI-powered job applications, interview preparation, and career support.\n\n"
    "With ApplyXAI, your students can get support with:\n"
    "• AI-assisted job applications\n"
    "• Resume and profile optimization\n"
    "• Interview preparation and coaching\n"
    "• Application and career progress tracking\n\n"
    "We would love to explore a Campus Partnership with {institute_name} and show you how ApplyXAI can support "
    "your students' placement journey.\n\n"
    "Create your institute account (takes a few minutes):\n{link}\n\n"
    "Reply to this email if you would like a short demo.\n\n"
    "If you prefer not to hear from us, reply with \"unsubscribe\".\n\n"
    "— Team ApplyXAI"
)


def proposal_image_public_url() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/outreach/campus-partnership-proposal.jpg"


def proposal_image_file_path():
    path = PROJECT_ROOT / "assets" / "outreach" / "campus-partnership-proposal.jpg"
    if path.is_file():
        return path
    alt = PROJECT_ROOT / "frontend" / "public" / "outreach" / "campus-partnership-proposal.jpg"
    return alt if alt.is_file() else path


def _template(db: Session) -> dict[str, str]:
    templates = ps.get_email_templates(db)
    auth = templates.get("auth") or {}
    row = auth.get("institute_proposal") or {}
    return {
        "subject": row.get("subject") or "ApplyXAI Campus partnership for {institute_name}",
        "body": row.get("body") or DEFAULT_EMAIL_BODY,
        "html": row.get("html") or "",
        "whatsapp": row.get("whatsapp") or DEFAULT_WHATSAPP_BODY,
    }


def _format(template: str, ctx: dict[str, str]) -> str:
    out = template
    for key, value in ctx.items():
        out = out.replace("{" + key + "}", value)
    return out


def _whatsapp_plain(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)


def _build_email_html(body: str, image_url: str, custom_html: str) -> str:
    if (custom_html or "").strip():
        return custom_html.replace("{proposal_image_url}", image_url)
    inner = text_to_html(body)
    return (
        f'{inner}<p style="margin-top:24px">'
        f'<img src="{image_url}" alt="ApplyXAI Campus Partnership" '
        f'style="max-width:100%;height:auto;border-radius:12px" /></p>'
    )


def generate_proposals(db: Session, profile: dict[str, Any]) -> tuple[str, str, str, str]:
    """Returns email subject, email body, email html, whatsapp body."""
    name = (profile.get("name") or "your institute").strip()
    contact = (profile.get("contact_name") or "there").strip()
    link = settings.FRONTEND_URL.rstrip("/") + "/register?account_type=institute"
    image_url = proposal_image_public_url()
    tpl = _template(db)
    ctx = {
        "app_name": settings.APP_NAME,
        "institute_name": name,
        "contact_name": contact,
        "link": link,
        "proposal_image_url": image_url,
    }
    subject = _format(tpl["subject"], ctx)
    body = _format(tpl["body"], ctx)

    try:
        ai_body = ai_service.complete(
            db,
            AiTask.APP_ANSWER,
            system="Write a concise, professional B2B partnership email for an Indian training institute. Plain text only.",
            user=(
                f"Institute: {name}\nPrograms: {', '.join(profile.get('programs') or [])}\n"
                f"City: {(profile.get('address') or {}).get('city', '')}\n"
                f"Base draft:\n{body}\n\nPersonalize in 120-180 words. Include unsubscribe line."
            ),
            feature="outreach",
            max_tokens=600,
        )
        if ai_body and len(ai_body.strip()) > 80:
            body = ai_body.strip()
    except Exception:
        logger.info("Using template proposal without AI personalization")

    html = _build_email_html(body, image_url, _format(tpl["html"], ctx))
    wa = _whatsapp_plain(_format(tpl["whatsapp"], ctx))
    return subject, body, html, wa
