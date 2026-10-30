"""Shared institute outreach discovery, crawl policy, identity, and contact extraction."""

from backend.app.services.outreach.contact_extract import extract_contacts_from_content
from backend.app.services.outreach.identity import discovery_dedupe_key, find_matching_lead, normalize_institute_name
from backend.app.services.outreach.search_queries import build_search_queries
from backend.app.services.outreach.url_normalize import normalize_url_for_compare, normalize_url_for_storage
from backend.app.services.outreach.url_safety import assert_url_safe_for_fetch, is_url_safe_for_fetch

__all__ = [
    "assert_url_safe_for_fetch",
    "build_search_queries",
    "discovery_dedupe_key",
    "extract_contacts_from_content",
    "find_matching_lead",
    "is_url_safe_for_fetch",
    "normalize_institute_name",
    "normalize_url_for_compare",
    "normalize_url_for_storage",
]
