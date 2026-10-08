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


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleEmailSender:
    def send(self, email: Email) -> None:
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
    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/verify-email?token={token}"
    return Email(
        to,
        f"Verify your {auth.app_name} email",
        f"Welcome to {auth.app_name}!\n\nConfirm your email address:\n{link}\n\n"
        f"This link expires in {auth.verification_hours} hours. "
        "If you didn't create an account, ignore this email.",
    )


def password_reset_email(to: str, token: str, db: Session | None = None) -> Email:
    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/reset-password?token={token}"
    return Email(
        to,
        f"Reset your {auth.app_name} password",
        f"Someone asked to reset the password for this {auth.app_name} account.\n\n"
        f"Choose a new password:\n{link}\n\n"
        f"This link expires in {auth.password_reset_minutes} minutes. "
        "If it wasn't you, ignore this email; your password is unchanged.",
    )


def account_exists_email(to: str, db: Session | None = None) -> Email:
    auth = ps.get_effective_auth(db)
    link = f"{auth.frontend_url}/forgot-password"
    return Email(
        to,
        f"Your {auth.app_name} account",
        f"Someone tried to register a new {auth.app_name} account with this email, "
        f"but you already have one.\n\nForgot your password? Reset it here:\n{link}\n\n"
        "If this wasn't you, you can ignore this email.",
    )


def notification_email(to: str, title: str, body: str, link: str, db: Session | None = None) -> Email:
    auth = ps.get_effective_auth(db)
    url = f"{auth.frontend_url}{link}" if link.startswith("/") else link
    text = f"{title}\n\n{body}".strip()
    if link:
        text += f"\n\nOpen in ApplyXAI:\n{url}"
    return Email(to, f"{auth.app_name}: {title}", text)
