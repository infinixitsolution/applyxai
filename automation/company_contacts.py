"""Contacts a job posting publishes: hiring-team name, email, or phone. Never the applicant."""

import re

_EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"(?<!\w)(\+?\d[\d\s().\-]{8,18}\d)(?!\w)")
_SKIP_EMAIL_HOSTS = ("linkedin.com", "example.com", "example.org", "sentry.io", "w3.org", "schema.org")


def _emails(text: str) -> list[str]:
    found = []
    for raw in _EMAIL.findall(text or ""):
        email = raw.strip().lower().rstrip(".")
        host = email.split("@", 1)[-1]
        if host.startswith("www."):
            host = host[4:]
        if any(host == skip or host.endswith("." + skip) for skip in _SKIP_EMAIL_HOSTS):
            continue
        if email.startswith("noreply@") or email.startswith("no-reply@"):
            continue
        if email not in found:
            found.append(email)
    return found[:8]


def _phones(text: str) -> list[str]:
    found = []
    for match in _PHONE.finditer(text or ""):
        raw = re.sub(r"\s+", " ", match.group(1)).strip(" .-")
        digits = re.sub(r"\D", "", raw)
        if not (10 <= len(digits) <= 15):
            continue
        if raw.startswith("+") or (len(digits) == 10 and digits[0] in "6789") or re.search(r"[\s().\-]", raw):
            if raw not in found:
                found.append(raw)
    return found[:8]


def _clean_name(name: str) -> tuple[str, str]:
    text = " ".join(str(name or "").replace("\r", "\n").split())
    if not text or text.lower() in {"unknown", "n/a", "na", "none"}:
        return "", ""
    parts = re.split(r"\s+(?:\u00b7|\|)\s+", text, maxsplit=1)
    person = parts[0].strip()
    role = parts[1].strip() if len(parts) > 1 else ""
    if len(person) < 2 or "@" in person or person.lower() in {"unknown", "hiring team"}:
        return "", ""
    return person[:120], role[:80]


def extract_published_contacts(text: str = "", *, name: str = "", link: str = "", role: str = "") -> list[dict]:
    """One row per published email or phone. A hiring-team name is kept when the page shows one."""
    person, parsed_role = _clean_name(name)
    role = (role or parsed_role or "")[:80]
    link = "" if not link or str(link).strip().lower() in {"unknown", "none"} else str(link).strip()[:500]
    emails, phones = _emails(text), _phones(text)
    rows: list[dict] = []
    if emails:
        for index, email in enumerate(emails):
            phone = ""
            if len(phones) == 1 and index == 0:
                phone = phones[0]
            elif index < len(phones) and len(phones) == len(emails):
                phone = phones[index]
            rows.append({
                "name": person if index == 0 else "",
                "email": email,
                "phone": phone,
                "role": role if index == 0 else "",
                "link": link if index == 0 else "",
            })
        if len(phones) > 1 and len(phones) != len(emails):
            for phone in phones:
                if any(row["phone"] == phone for row in rows):
                    continue
                rows.append({"name": "", "email": "", "phone": phone, "role": "", "link": ""})
    elif phones:
        for index, phone in enumerate(phones):
            rows.append({
                "name": person if index == 0 else "",
                "email": "",
                "phone": phone,
                "role": role if index == 0 else "",
                "link": link if index == 0 else "",
            })
    elif person:
        rows.append({"name": person, "email": "", "phone": "", "role": role, "link": link})
    return rows


def contact_key(row: dict) -> str:
    email = str(row.get("email") or "").strip().lower()
    phone = re.sub(r"\D", "", str(row.get("phone") or ""))
    name = str(row.get("name") or "").strip().lower()
    if email:
        return f"e:{email}"
    if phone:
        return f"p:{phone}"
    if name:
        return f"n:{name}"
    return ""


def merge_contacts(*groups: list) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for raw in group:
            if not isinstance(raw, dict):
                continue
            row = {
                "name": str(raw.get("name") or "")[:120],
                "email": str(raw.get("email") or "")[:320],
                "phone": str(raw.get("phone") or "")[:40],
                "role": str(raw.get("role") or "")[:80],
                "link": str(raw.get("link") or "")[:500],
            }
            key = contact_key(row)
            if not key:
                continue
            current = merged.get(key)
            if current is None:
                merged[key] = row
                order.append(key)
                continue
            for field in ("name", "email", "phone", "role", "link"):
                if not current[field] and row[field]:
                    current[field] = row[field]
    return [merged[key] for key in order]
