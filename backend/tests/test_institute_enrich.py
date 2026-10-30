"""Institute lead enrichment parsing."""

from backend.app.services import institute_enrich_service as enrich
from backend.app.services.firecrawl_client import _normalize_search_hits


def test_parse_profile_string_field_confidence():
    raw = """{
        "name": "ABC Training",
        "field_confidence": "not-a-dict",
        "emails": ["a@example.com"]
    }"""
    profile = enrich._parse_profile(raw, fallback_name="Fallback", fallback_url="https://example.com")
    assert profile["name"] == "ABC Training"
    assert profile["field_confidence"] == {}
    assert enrich._confidence_from_profile(profile) == 0.5


def test_completeness_score_uses_lead_display_name_and_whatsapp():
    from types import SimpleNamespace

    from backend.app.services import institute_enrich_service as enrich

    lead = SimpleNamespace(
        display_name="Shiva Institute",
        source_url="",
        whatsapp_phone="+918197106573",
        completeness_score=0,
        profile=None,
    )
    assert enrich.completeness_score(enrich.scoring_payload_for_lead(lead)) == 40
    assert enrich.sync_lead_completeness_score(lead) is True
    assert lead.completeness_score == 40


def test_completeness_score_parses_comma_separated_emails():
    from backend.app.services import institute_enrich_service as enrich

    assert enrich.completeness_score({"name": "X", "emails": "a@b.com, c@d.com"}) == 45


def test_merge_profiles_keeps_existing_emails():
    from backend.app.services import institute_enrich_service as enrich

    old = {"name": "ABC", "emails": ["keep@example.com"], "phones": [], "address": {"city": "Bangalore"}}
    new = {"name": "ABC Institute", "emails": [], "phones": ["+919876543210"], "description": "IT training"}
    merged = enrich.merge_profiles(old, new)
    assert "keep@example.com" in merged["emails"]
    assert "+919876543210" in merged["phones"]
    assert merged["description"] == "IT training"


def test_normalize_search_hits_v2_web_bucket():
    body = {
        "success": True,
        "data": {
            "web": [
                {"url": "https://a.com", "title": "A Institute"},
                {"url": "https://b.com", "title": "B Institute"},
            ]
        },
    }
    hits = _normalize_search_hits(body)
    assert len(hits) == 2
    assert hits[0]["url"] == "https://a.com"
