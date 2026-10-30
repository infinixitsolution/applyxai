"""Institute identity normalization and conservative duplicate matching."""

from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.models.outreach import InstituteLead
from backend.app.services.outreach.aggregators import host_of, is_aggregator_url, looks_like_official_site
from backend.app.services.outreach.url_normalize import normalize_url_for_compare, url_identity_key

_SUFFIX_RE = re.compile(r"\b(pvt\.?|ltd\.?|llp|inc\.?|co\.?)\b", re.I)


def normalize_institute_name(name: str) -> str:
    text = re.sub(r"\s+", " ", (name or "").strip().lower())
    text = _SUFFIX_RE.sub("", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:120]


def discovery_dedupe_key(url: str, title: str) -> str:
    """Path-aware listing key — distinct institutes on the same aggregator domain stay separate."""
    identity = url_identity_key(url)
    if identity:
        return f"listing:{identity}"[:512]
    slug = re.sub(r"[^a-z0-9]+", "-", (title or url).lower()).strip("-")[:200]
    return f"title:{slug or 'unknown'}"[:512]


def official_site_dedupe_key(website: str, name: str) -> str | None:
    if not website or not looks_like_official_site(website):
        return None
    host = host_of(website)
    if not host:
        return None
    norm_name = normalize_institute_name(name)
    if norm_name:
        return f"official:{host}:{norm_name}"[:512]
    return f"official:{host}"[:512]


def _phones_from_payload(payload: dict) -> list[str]:
    phones = payload.get("phones")
    if not isinstance(phones, list):
        return []
    return [re.sub(r"\D", "", str(p))[-10:] for p in phones if str(p).strip()]


def find_matching_lead(
    db: Session,
    *,
    dedupe_key: str,
    discovery_url: str,
    title: str,
    official_website: str = "",
    city: str = "",
) -> tuple[InstituteLead | None, str]:
    """
    Return (lead, match_reason). Conservative: only auto-match on strong keys.
    """
    existing = db.scalar(
        select(InstituteLead)
        .options(joinedload(InstituteLead.profile))
        .where(InstituteLead.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return existing, "listing_key"

    # Legacy host-only keys from older scrapes (same URL host on aggregator — do not use for new listings)
    legacy_host = host_of(discovery_url)
    if legacy_host and is_aggregator_url(discovery_url):
        pass
    else:
        legacy_key = f"host:{legacy_host}" if legacy_host else ""
        if legacy_key:
            legacy = db.scalar(
                select(InstituteLead)
                .options(joinedload(InstituteLead.profile))
                .where(InstituteLead.dedupe_key == legacy_key)
            )
            if legacy is not None and not is_aggregator_url(discovery_url):
                return legacy, "legacy_host"

    site_key = official_site_dedupe_key(official_website, title)
    if site_key:
        by_site = db.scalar(
            select(InstituteLead)
            .options(joinedload(InstituteLead.profile))
            .where(InstituteLead.dedupe_key == site_key)
        )
        if by_site is not None:
            return by_site, "official_site"

    norm_title = normalize_institute_name(title)
    norm_city = normalize_institute_name(city)
    if norm_title and norm_city and len(norm_title) >= 6:
        candidates = db.scalars(
            select(InstituteLead)
            .options(joinedload(InstituteLead.profile))
            .where(
                InstituteLead.display_name.ilike(f"%{title[:40]}%"),
            )
            .limit(20)
        ).all()
        for cand in candidates:
            payload = cand.profile.payload if cand.profile and isinstance(cand.profile.payload, dict) else {}
            addr = payload.get("address") if isinstance(payload.get("address"), dict) else {}
            cand_city = normalize_institute_name(str(addr.get("city") or ""))
            if cand_city == norm_city and normalize_institute_name(cand.display_name) == norm_title:
                return cand, "name_city"

    return None, ""


def merge_identity_keys_on_official_site(lead: InstituteLead, *, website: str, name: str) -> bool:
    """When official website is verified, upgrade dedupe_key if still on listing key."""
    new_key = official_site_dedupe_key(website, name)
    if not new_key or lead.dedupe_key == new_key:
        return False
    if lead.dedupe_key.startswith("listing:") and looks_like_official_site(website):
        lead.dedupe_key = new_key
        return True
    return False
