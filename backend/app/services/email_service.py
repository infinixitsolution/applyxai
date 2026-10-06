"""Outgoing email. SMTP when SMTP_HOST is set; otherwise logged to the console (development)."""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from backend.app.core.config import settings

logger = logging.getLogger("applyxai.email")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleEmailSender:
    """Development only: production refuses to start without SMTP_HOST (see config.py)."""

    def send(self, email: Email) -> None:
        logger.warning("DEV EMAIL to %s | %s\n%s", email.to, email.subject, email.body)


class SmtpEmailSender:
    def send(self, email: Email) -> None:
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.body)
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        except Exception:
            # Runs as a background task: log and move on rather than failing the request.
            logger.exception("Failed to send email '%s'", email.subject)


@lru_cache
def get_email_sender() -> EmailSender:
    return SmtpEmailSender() if settings.SMTP_HOST else ConsoleEmailSender()


def verification_email(to: str, token: str) -> Email:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    return Email(to, f"Verify your {settings.APP_NAME} email",
                 f"Welcome to {settings.APP_NAME}!\n\nConfirm your email address:\n{link}\n\n"
                 f"This link expires in {settings.EMAIL_VERIFICATION_HOURS} hours. "
                 "If you didn't create an account, ignore this email.")


def password_reset_email(to: str, token: str) -> Email:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    return Email(to, f"Reset your {settings.APP_NAME} password",
                 f"Someone asked to reset the password for this {settings.APP_NAME} account.\n\n"
                 f"Choose a new password:\n{link}\n\n"
                 f"This link expires in {settings.PASSWORD_RESET_MINUTES} minutes. "
                 "If it wasn't you, ignore this email; your password is unchanged.")


def account_exists_email(to: str) -> Email:
    link = f"{settings.FRONTEND_URL}/forgot-password"
    return Email(to, f"Your {settings.APP_NAME} account",
                 f"Someone tried to register a new {settings.APP_NAME} account with this email, "
                 f"but you already have one.\n\nForgot your password? Reset it here:\n{link}\n\n"
                 "If this wasn't you, you can ignore this email.")
