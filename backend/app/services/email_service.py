"""Outgoing email. SMTP from platform settings (DB) or environment; otherwise console (development)."""

import html as html_lib
import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.services import platform_settings_service as ps

logger = logging.getLogger("applyxai.email")

SMTPS_PORT = 465


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    html: str = ""


FOOTER_LINES = ("Regards,", "ApplyXAI", "www.applyxai.com", "Bangalore", "info@applyxai.com")
_FOOTER_MARKER = "info@applyxai.com"
_LAYOUT_MARKER = "<!-- applyxai-layout -->"
SITE_URL = "https://www.applyxai.com"
# Mail clients load images from the public site, never from localhost, and most block SVG.
LOGO_URL = "https://applyxai.com/email-logo.png"
_BRAND = "#2563eb"
_FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_URL = re.compile(r"(https?://[^\s<>\"']+)")
_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)


def _inline(text: str) -> str:
    """Escape one line of plain text and turn bare URLs into links."""
    parts = _URL.split(text)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            url = html_lib.escape(part, quote=True)
            out.append(f'<a href="{url}" style="color:{_BRAND};word-break:break-all">{url}</a>')
        else:
            out.append(html_lib.escape(part))
    return "".join(out)


def _button(label: str, url: str) -> str:
    url = html_lib.escape(url, quote=True)
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 20px">'
        f'<tr><td style="border-radius:10px;background:{_BRAND}">'
        f'<a href="{url}" style="display:inline-block;padding:12px 24px;{_FONT};font-size:15px;font-weight:600;'
        f'color:#ffffff;text-decoration:none;border-radius:10px">{html_lib.escape(label)}</a>'
        "</td></tr></table>"
        f'<p style="margin:0 0 20px;font-size:12px;line-height:1.5;color:#94a3b8">'
        f'Or paste this link into your browser:<br><a href="{url}" style="color:#64748b;word-break:break-all">{url}</a></p>'
    )


def text_to_html(body: str) -> str:
    """Plain-text email body as HTML: a short first line becomes the heading, "Label:" + URL becomes a button."""
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", body.strip()) if b.strip()]
    out = []
    for index, block in enumerate(blocks):
        lines = [line.rstrip() for line in block.split("\n")]
        if index == 0 and len(lines) == 1 and len(lines[0]) <= 80 and len(blocks) > 1 and not _URL.search(lines[0]):
            out.append(f'<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:#0f172a">{html_lib.escape(lines[0])}</h1>')
            continue
        para: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if line.endswith(":") and _URL.fullmatch(nxt):
                if para:
                    out.append(_paragraph(para))
                    para = []
                out.append(_button(line[:-1].strip(), nxt))
                i += 2
                continue
            if _URL.fullmatch(line.strip()) and not para:
                out.append(_button("Open link", line.strip()))
                i += 1
                continue
            para.append(_inline(line))
            i += 1
        if para:
            out.append(_paragraph(para))
    return "".join(out)


def _paragraph(lines: list[str]) -> str:
    return f'<p style="margin:0 0 16px;font-size:15px;line-height:1.65;color:#334155">{"<br>".join(lines)}</p>'


def render_layout(subject: str, content_html: str) -> str:
    """Wrap email content in the ApplyXAI header (logo) and footer (logo, signature, contact)."""
    title = html_lib.escape(subject)
    year = datetime.now(timezone.utc).year
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;{_FONT}">{_LAYOUT_MARKER}
<span style="display:none;max-height:0;overflow:hidden;opacity:0">{title}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9">
<tr><td align="center" style="padding:32px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(15,23,42,.08)">
<tr><td style="background:#0f172a;background-image:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);padding:22px 32px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle"><a href="{SITE_URL}"><img src="{LOGO_URL}" width="44" height="44" alt="ApplyXAI" style="display:block;border:0;border-radius:12px;background:#ffffff"></a></td>
<td style="vertical-align:middle;padding-left:12px"><a href="{SITE_URL}" style="{_FONT};font-size:20px;font-weight:700;color:#ffffff;text-decoration:none">Apply<span style="color:#60a5fa">XAI</span></a>
<div style="{_FONT};font-size:12px;color:#cbd5e1;margin-top:2px">Apply smarter on LinkedIn</div></td>
</tr></table></td></tr>
<tr><td style="padding:32px;{_FONT};color:#334155">{content_html}</td></tr>
<tr><td style="padding:0 32px"><div style="border-top:1px solid #e2e8f0"></div></td></tr>
<tr><td style="padding:24px 32px 28px;{_FONT}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="56" style="vertical-align:top"><img src="{LOGO_URL}" width="44" height="44" alt="ApplyXAI" style="display:block;border:0;border-radius:12px"></td>
<td style="vertical-align:top;font-size:14px;line-height:1.6;color:#475569">Regards,<br><strong style="color:#0f172a">ApplyXAI</strong><br>
<a href="{SITE_URL}" style="color:{_BRAND};text-decoration:none">www.applyxai.com</a><br>Bangalore<br>
<a href="mailto:info@applyxai.com" style="color:{_BRAND};text-decoration:none">info@applyxai.com</a></td>
</tr></table></td></tr>
</table>
<p style="margin:20px 0 0;{_FONT};font-size:12px;line-height:1.5;color:#94a3b8">You're receiving this email because of your ApplyXAI account.<br>&copy; {year} ApplyXAI &middot; Bangalore, India</p>
</td></tr></table></body></html>"""


def branded(email: Email) -> Email:
    """Every outgoing email: text ends with the signature, HTML gets the branded header and footer (each added once)."""
    body = email.body.rstrip()
    if _FOOTER_MARKER not in body:
        body = f"{body}\n\n" + "\n".join(FOOTER_LINES)
    html = email.html
    if _LAYOUT_MARKER not in html:
        if html.strip():
            match = _BODY.search(html)
            content = match.group(1) if match else html
        else:
            content = text_to_html(email.body)
        html = render_layout(email.subject, content)
    return Email(to=email.to, subject=email.subject, body=body, html=html)


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleEmailSender:
    def send(self, email: Email) -> None:
        email = branded(email)
        logger.warning("DEV EMAIL to %s | %s\n%s", email.to, email.subject, email.body)


class SmtpEmailSender:
    def __init__(self, smtp: ps.EffectiveSmtp):
        self._smtp = smtp

    def deliver(self, email: Email) -> None:
        message = EmailMessage()
        message["From"] = self._smtp.from_address
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.body)
        if email.html.strip():
            message.add_alternative(email.html, subtype="html")
        context = ssl.create_default_context()
        if self._smtp.port == SMTPS_PORT:
            client = smtplib.SMTP_SSL(self._smtp.host, self._smtp.port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(self._smtp.host, self._smtp.port, timeout=15)
        with client:
            if self._smtp.port != SMTPS_PORT:
                client.starttls(context=context)
            if self._smtp.username:
                client.login(self._smtp.username, self._smtp.password)
            client.send_message(message)

    def send(self, email: Email) -> None:
        try:
            self.deliver(branded(email))
        except Exception:
            logger.exception("Failed to send email '%s'", email.subject)


def get_email_sender(db: Session | None = None) -> EmailSender:
    smtp = ps.get_effective_smtp(db)
    if smtp.configured:
        return SmtpEmailSender(smtp)
    return ConsoleEmailSender()


def smtp_configured(db: Session | None = None) -> bool:
    return ps.get_effective_smtp(db).configured


def email_settings(db: Session | None = None) -> dict:
    smtp = ps.get_effective_smtp(db)
    auth = ps.get_effective_auth(db)
    return {
        "mode": "smtp" if smtp.configured else "console",
        "host": smtp.host,
        "port": smtp.port,
        "security": "ssl" if smtp.port == SMTPS_PORT else "starttls",
        "from": smtp.from_address,
        "authenticated": bool(smtp.username),
        "require_verification": auth.require_verification,
        "verification_hours": auth.verification_hours,
        "frontend_url": auth.frontend_url,
    }


def sample_email(to: str, db: Session | None = None) -> Email:
    auth = ps.get_effective_auth(db)
    return Email(
        to,
        f"{auth.app_name} test email",
        f"This is a test email from the {auth.app_name} admin area.\n\nIf you can read it, outgoing email works.",
    )


def verification_email(to: str, token: str, db: Session | None = None) -> Email:
    from backend.app.services import template_service as ts

    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/verify-email?token={token}"
    email = ts.auth_email(db, "verify_email", to, link=link, verification_hours=str(auth.verification_hours))
    return Email(to=to, subject=email.subject, body=email.body, html=email.html)


def password_reset_email(to: str, token: str, db: Session | None = None) -> Email:
    from backend.app.services import template_service as ts

    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/reset-password?token={token}"
    email = ts.auth_email(db, "password_reset", to, link=link, password_reset_minutes=str(auth.password_reset_minutes))
    return Email(to=to, subject=email.subject, body=email.body, html=email.html)


def account_exists_email(to: str, db: Session | None = None) -> Email:
    from backend.app.services import template_service as ts

    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/forgot-password"
    email = ts.auth_email(db, "account_exists", to, link=link)
    return Email(to=to, subject=email.subject, body=email.body, html=email.html)


def institute_invite_email(to: str, institute_name: str, token: str, db: Session | None = None) -> Email:
    from backend.app.services import template_service as ts

    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/invite/{token}?token={token}"
    email = ts.auth_email(db, "institute_invite", to, link=link, institute_name=institute_name)
    return Email(to=to, subject=email.subject, body=email.body, html=email.html)


def notification_email(
    to: str, subject: str, body: str, link: str, db: Session | None = None, *, html: str = ""
) -> Email:
    if html.strip():
        return Email(to, subject, body, html=html)
    auth = ps.get_effective_auth(db)
    url = f"{auth.frontend_url}{link}" if link.startswith("/") else link
    text = body.strip()
    if link and "Open in" not in text:
        text += f"\n\nOpen in {auth.app_name}:\n{url}"
    return Email(to, subject, text)


def auth_template_test_email(db: Session, kind: str, to: str) -> Email:
    """Send a sample auth template with placeholder links for admin testing."""
    from backend.app.services import template_service as ts

    auth = ps.get_effective_auth(db)
    sample_link = f"{auth.frontend_url}/example"
    vars_common = {"to": to, "link": sample_link, "institute_name": "Example Institute"}
    email = ts.auth_email(db, kind, to, **vars_common)
    return Email(to=to, subject=email.subject, body=email.body, html=email.html)
