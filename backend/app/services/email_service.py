"""Outgoing email. SMTP from platform settings (DB) or environment; otherwise console (development)."""

import logging
import smtplib
import ssl
from dataclasses import dataclass
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


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleEmailSender:
    def send(self, email: Email) -> None:
        extra = f"\n[HTML]\n{email.html}" if email.html else ""
        logger.warning("DEV EMAIL to %s | %s\n%s%s", email.to, email.subject, email.body, extra)


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
            self.deliver(email)
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
