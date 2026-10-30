"""Merge deterministic evidence with AI output — reject unsupported contact facts."""

from __future__ import annotations

import re
from typing import Any

from backend.app.services.institute_enrich_service import merge_profiles
from backend.app.services.outreach.aggregators import is_aggregator_url, looks_like_official_site
from backend.app.services.outreach.contact_extract import ContactCandidate, candidates_to_profile_lists


def _in_source_blob(value: str, blob: str) -> bool:
    if not value or not blob:
        return False
    v = value.lower().strip()
    if v in blob.lower():
        return True
    digits = re.sub(r"\D", "", value)
    if digits and digits[-10:] in re.sub(r"\D", "", blob):
        return True
    return False


def apply_evidence_gate(
    ai_profile: dict[str, Any],
    *,
    source_blob: str,
    deterministic: list[ContactCandidate],
    fallback_name: str,
    discovery_url: str,
) -> dict[str, Any]:
    """Keep AI narrative fields only when supported; contacts must appear in evidence."""
    det_emails, det_phones, contact_evidence = candidates_to_profile_lists(deterministic)
    out = dict(ai_profile)

    ai_emails = [str(e).strip().lower() for e in (out.get("emails") or []) if str(e).strip()]
    ai_phones = [str(p).strip() for p in (out.get("phones") or []) if str(p).strip()]

    confirmed_emails = list(det_emails)
    for em in ai_emails:
        if em in confirmed_emails:
            continue
        if _in_source_blob(em, source_blob):
            confirmed_emails.append(em)

    confirmed_phones = list(det_phones)
    for ph in ai_phones:
        if ph in confirmed_phones:
            continue
        if _in_source_blob(ph, source_blob):
            confirmed_phones.append(ph)

    out["emails"] = confirmed_emails[:5]
    out["phones"] = confirmed_phones[:5]

    website = str(out.get("website") or "").strip()
    if website and is_aggregator_url(website):
        out["website"] = ""
        out.setdefault("notes", "")
        out["notes"] = (str(out.get("notes") or "") + "\n[website:aggregator_skipped]").strip()
    if not out.get("website") and looks_like_official_site(discovery_url):
        out["website"] = discovery_url
    elif not out.get("website") and discovery_url and not is_aggregator_url(discovery_url):
        out["website_unverified"] = discovery_url

    out["contact_candidates"] = contact_evidence
    out.setdefault("field_evidence", {})
    fe = out["field_evidence"] if isinstance(out["field_evidence"], dict) else {}
    fe["emails"] = [e for e in contact_evidence if e.get("field") == "emails"]
    fe["phones"] = [e for e in contact_evidence if e.get("field") == "phones"]
    out["field_evidence"] = fe

    if not str(out.get("name") or "").strip():
        out["name"] = fallback_name[:190]

    return out


def merge_lead_payload(
    previous: dict[str, Any],
    incoming: dict[str, Any],
    *,
    source_blob: str,
) -> dict[str, Any]:
    """Merge without wiping good data; incoming empty contacts do not erase previous."""
    if not previous:
        return incoming
    merged = merge_profiles(previous, incoming)
    for field in ("emails", "phones"):
        prev = previous.get(field) if isinstance(previous.get(field), list) else []
        new = incoming.get(field) if isinstance(incoming.get(field), list) else []
        if not new and prev:
            merged[field] = prev
    prev_ev = previous.get("contact_candidates") if isinstance(previous.get("contact_candidates"), list) else []
    new_ev = incoming.get("contact_candidates") if isinstance(incoming.get("contact_candidates"), list) else []
    combined = { (e.get("field"), e.get("value")): e for e in prev_ev if isinstance(e, dict) }
    for e in new_ev:
        if isinstance(e, dict):
            combined[(e.get("field"), e.get("value"))] = e
    merged["contact_candidates"] = list(combined.values())[:30]
    return merged
