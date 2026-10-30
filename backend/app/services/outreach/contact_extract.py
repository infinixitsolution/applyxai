"""Deterministic contact extraction with provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from backend.app.services.institute_enrich_service import _EMAIL_RE, _PHONE_RE, _normalize_phone

_PLACEHOLDER_EMAILS = frozenset(
    {
        "example.com",
        "email@example.com",
        "you@example.com",
        "name@example.com",
        "test@test.com",
        "user@domain.com",
    }
)
_MAILTO_RE = re.compile(r"mailto:([^\s\"'<>?#]+)", re.I)
_TEL_RE = re.compile(r"tel:([+\d\s().-]+)", re.I)


@dataclass
class ContactCandidate:
    value: str
    field: str  # emails | phones
    status: str  # candidate | syntax_valid | invalid
    source_url: str
    method: str
    raw_value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "field": self.field,
            "status": self.status,
            "source_url": self.source_url,
            "method": self.method,
            "raw_value": self.raw_value or self.value,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }


def _email_syntax_ok(email: str) -> bool:
    e = email.strip().lower()
    if not e or "@" not in e:
        return False
    if not _EMAIL_RE.fullmatch(e):
        return False
    if any(e.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return False
    domain = e.split("@", 1)[1]
    if domain in _PLACEHOLDER_EMAILS or "example.com" in domain:
        return False
    if "sentry.io" in domain or "wixpress.com" in domain:
        return False
    return True


def _phone_syntax_ok(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10


def extract_contacts_from_content(text: str, *, source_url: str, html: str | None = None) -> list[ContactCandidate]:
    blob = "\n".join(p for p in (text or "", html or "") if p)
    if not blob.strip():
        return []

    found: list[ContactCandidate] = []
    seen_email: set[str] = set()
    seen_phone: set[str] = set()

    for match in _MAILTO_RE.finditer(blob):
        raw = unquote(match.group(1)).split("?")[0].strip()
        val = raw.lower()
        if val in seen_email:
            continue
        seen_email.add(val)
        status = "syntax_valid" if _email_syntax_ok(val) else "invalid"
        found.append(
            ContactCandidate(value=val, field="emails", status=status, source_url=source_url, method="mailto", raw_value=raw)
        )

    for match in _TEL_RE.finditer(blob):
        raw = match.group(1).strip()
        val = _normalize_phone(raw)
        key = re.sub(r"\D", "", val)[-10:]
        if not key or key in seen_phone:
            continue
        seen_phone.add(key)
        status = "syntax_valid" if _phone_syntax_ok(val) else "invalid"
        found.append(
            ContactCandidate(value=val, field="phones", status=status, source_url=source_url, method="tel", raw_value=raw)
        )

    for match in _EMAIL_RE.finditer(blob):
        val = match.group(0).lower()
        if val in seen_email:
            continue
        if not _email_syntax_ok(val):
            continue
        seen_email.add(val)
        found.append(
            ContactCandidate(value=val, field="emails", status="syntax_valid", source_url=source_url, method="regex")
        )

    for match in _PHONE_RE.finditer(blob):
        raw = match.group(0)
        val = _normalize_phone(raw)
        key = re.sub(r"\D", "", val)[-10:]
        if not key or key in seen_phone:
            continue
        if not _phone_syntax_ok(val):
            continue
        seen_phone.add(key)
        found.append(
            ContactCandidate(value=val, field="phones", status="syntax_valid", source_url=source_url, method="regex", raw_value=raw)
        )

    return found


def candidates_to_profile_lists(candidates: list[ContactCandidate]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    emails: list[str] = []
    phones: list[str] = []
    evidence: list[dict[str, Any]] = []
    for c in candidates:
        evidence.append(c.to_dict())
        if c.status != "syntax_valid":
            continue
        if c.field == "emails" and c.value not in emails:
            emails.append(c.value)
        if c.field == "phones" and c.value not in phones:
            phones.append(c.value)
    return emails[:5], phones[:5], evidence
