"""Verified outreach scrape pipeline: crawl, contacts, identity, Firecrawl outcomes."""

from unittest.mock import patch

import pytest

from backend.app.models.outreach import InstituteLead, InstituteLeadProfile, InstituteScrapeJob
from backend.app.services import institute_scrape_service as scrape
from backend.app.services.firecrawl_client import FirecrawlScrapeOutcome, FirecrawlSearchOutcome
from backend.app.services.outreach.contact_extract import extract_contacts_from_content
from backend.app.services.outreach.evidence import apply_evidence_gate
from backend.app.services.outreach.identity import discovery_dedupe_key, find_matching_lead
from backend.app.services.outreach.search_queries import build_search_queries
from backend.app.services.outreach.url_safety import is_url_safe_for_fetch


def test_build_search_queries_avoids_duplicate_training_phrase():
    queries = build_search_queries(
        keyword="IT training institute",
        location="Bangalore",
        sources=["google"],
        max_queries=1,
    )
    assert len(queries) == 1
    assert queries[0][1].lower().count("training institute") == 1


def test_two_institutes_on_justdial_get_distinct_dedupe_keys():
    a = discovery_dedupe_key("https://www.justdial.com/bangalore/abc-institute", "ABC")
    b = discovery_dedupe_key("https://www.justdial.com/bangalore/xyz-institute", "XYZ")
    assert a != b
    assert a.startswith("listing:")
    assert b.startswith("listing:")


def test_extract_mailto_and_multiple_emails():
    html = '<a href="mailto:adm@institute.in">Email</a> Also reach info@institute.in'
    found = extract_contacts_from_content(html, source_url="https://institute.in/contact", html=html)
    emails = [c.value for c in found if c.field == "emails" and c.status == "syntax_valid"]
    assert "adm@institute.in" in emails
    assert "info@institute.in" in emails


def test_ai_cannot_create_unsupported_contacts():
    blob = "ABC Institute offers courses in Python."
    deterministic = extract_contacts_from_content(blob, source_url="https://example.com")
    ai_guess = {
        "name": "ABC Institute",
        "emails": ["fake@not-in-source.com"],
        "phones": ["+919999999999"],
        "website": "https://example.com",
        "address": {},
        "programs": [],
    }
    gated = apply_evidence_gate(
        ai_guess,
        source_blob=blob,
        deterministic=deterministic,
        fallback_name="ABC",
        discovery_url="https://example.com",
    )
    assert gated["emails"] == []
    assert gated["phones"] == []


def test_private_network_url_rejected():
    assert is_url_safe_for_fetch("http://127.0.0.1/admin") is False
    assert is_url_safe_for_fetch("http://localhost/") is False


@pytest.fixture
def scrape_job(db):
    job = InstituteScrapeJob(
        query="IT training",
        location="Pune",
        sources=["google"],
        max_results=5,
        status="running",
        stats=scrape._empty_stats(),
    )
    db.add(job)
    db.commit()
    return job


@patch("backend.app.services.institute_scrape_service.firecrawl_client.scrape_url_with_outcome")
@patch("backend.app.services.institute_scrape_service.firecrawl_client.search_web_with_outcome")
@patch("backend.app.services.institute_scrape_service.institute_enrich_service.enrich_from_snippets")
def test_long_snippet_official_site_is_scraped(mock_enrich, mock_search, mock_scrape, db, scrape_job, monkeypatch):
    monkeypatch.setattr(scrape, "check_scrape_prerequisites", lambda _db: None)
    long_snippet = "x" * 250
    mock_search.return_value = FirecrawlSearchOutcome(
        ok=True,
        hits=[{"url": "https://real-institute.in", "title": "Real Institute", "description": long_snippet}],
    )
    mock_scrape.return_value = FirecrawlScrapeOutcome(
        ok=True,
        data={"markdown": "Contact admissions@real-institute.in +919876543210"},
    )
    mock_enrich.return_value = (
        {"name": "Real Institute", "emails": [], "phones": [], "website": "https://real-institute.in", "address": {}},
        0.5,
    )

    scrape.run_scrape_job(db, scrape_job.id)
    db.commit()

    assert mock_scrape.called
    from sqlalchemy import select

    lead = db.scalar(select(InstituteLead).where(InstituteLead.display_name.ilike("%Real%")))
    assert lead is not None
    assert lead.profile.payload.get("emails")


def test_two_institutes_on_same_directory_are_not_merged(db, scrape_job):
    key_a = discovery_dedupe_key("https://justdial.com/pune/alpha-training", "Alpha")
    key_b = discovery_dedupe_key("https://justdial.com/pune/beta-training", "Beta")
    assert key_a != key_b

    la, created_a, _ = scrape._upsert_lead(
        db,
        job=scrape_job,
        platform="google",
        url="https://justdial.com/pune/alpha-training",
        title="Alpha Training",
        snippet="Alpha snippet",
        city="Pune",
    )
    lb, created_b, _ = scrape._upsert_lead(
        db,
        job=scrape_job,
        platform="google",
        url="https://justdial.com/pune/beta-training",
        title="Beta Training",
        snippet="Beta snippet",
        city="Pune",
    )
    assert created_a and created_b
    assert la.id != lb.id


def test_firecrawl_failure_visible_in_job_result(db, scrape_job, monkeypatch):
    monkeypatch.setattr(scrape, "check_scrape_prerequisites", lambda _db: None)
    with patch(
        "backend.app.services.institute_scrape_service.firecrawl_client.search_web_with_outcome",
        return_value=FirecrawlSearchOutcome(ok=False, error_code="FIRECRAWL_AUTH", error_message="Invalid key"),
    ):
        scrape.run_scrape_job(db, scrape_job.id)
    db.commit()
    job = db.get(InstituteScrapeJob, scrape_job.id)
    assert job.status == "failed"
    assert "Invalid key" in job.error_message
