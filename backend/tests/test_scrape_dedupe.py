"""Scrape job deduplication merges new institute data into existing leads."""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from backend.app.models.outreach import InstituteLead, InstituteLeadProfile, InstituteScrapeJob
from backend.app.services import institute_scrape_service as scrape


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


def test_upsert_duplicate_appends_snippet_and_merges_profile(db, scrape_job):
    lead = InstituteLead(
        dedupe_key="host:example.com",
        display_name="Example Institute",
        source_url="https://example.com",
        source_platform="google",
        status="enriched",
        completeness_score=45,
    )
    db.add(lead)
    db.flush()
    db.add(
        InstituteLeadProfile(
            lead_id=lead.id,
            payload={
                "name": "Example Institute",
                "emails": ["old@example.com"],
                "phones": [],
                "website": "https://example.com",
                "address": {"city": "Pune", "line": "", "state": "", "country": "India", "pin": ""},
            },
            raw_snippets=["Original listing blurb about courses."],
        )
    )
    db.commit()

    lead2, created, new_content = scrape._upsert_lead(
        db,
        job=scrape_job,
        platform="google",
        url="https://example.com/contact",
        title="Example Institute Contact",
        snippet="New phone +919876543210 and email admissions@example.com on contact page.",
        city="Pune",
        official_website="https://example.com",
    )
    assert created is False
    assert lead2.id == lead.id
    assert new_content is True
    assert len(lead2.profile.raw_snippets) == 2

    lead3, created2, new_content2 = scrape._upsert_lead(
        db,
        job=scrape_job,
        platform="google",
        url="https://example.com/contact",
        title="Example Institute Contact",
        snippet="New phone +919876543210 and email admissions@example.com on contact page.",
        city="Pune",
    )
    assert created2 is False
    assert new_content2 is False


def test_append_raw_snippet_detects_near_duplicates():
    profile = InstituteLeadProfile(payload={}, raw_snippets=["Same text about institute."])
    assert scrape._append_raw_snippet(profile, "Same text about institute.") is False
    assert scrape._append_raw_snippet(profile, "Different details about placements.") is True


@patch("backend.app.services.institute_scrape_service.firecrawl_client.search_web_with_outcome")
@patch("backend.app.services.institute_scrape_service.firecrawl_client.scrape_url_with_outcome")
@patch("backend.app.services.institute_scrape_service.institute_enrich_service.enrich_from_snippets")
def test_run_scrape_skips_duplicate_without_new_data(mock_enrich, mock_scrape_url, mock_search, db, scrape_job, monkeypatch):
    from backend.app.services.firecrawl_client import FirecrawlScrapeOutcome, FirecrawlSearchOutcome

    monkeypatch.setattr(scrape, "check_scrape_prerequisites", lambda _db: None)
    mock_search.return_value = FirecrawlSearchOutcome(
        ok=True,
        hits=[
            {"url": "https://dup.com", "title": "Dup Institute", "description": "Already seen snippet."},
            {"url": "https://new.com", "title": "New Institute", "description": "Brand new listing."},
        ],
    )
    mock_scrape_url.return_value = FirecrawlScrapeOutcome(ok=True, data={"markdown": ""})
    mock_enrich.return_value = (
        {"name": "New Institute", "emails": ["new@new.com"], "phones": [], "website": "https://new.com", "address": {}},
        0.8,
    )

    existing = InstituteLead(
        dedupe_key="host:dup.com",
        display_name="Dup Institute",
        source_url="https://dup.com",
        source_platform="google",
    )
    db.add(existing)
    db.flush()
    db.add(
        InstituteLeadProfile(
            lead_id=existing.id,
            payload={"name": "Dup Institute", "emails": [], "phones": []},
            raw_snippets=["Already seen snippet."],
        )
    )
    db.commit()

    scrape.run_scrape_job(db, scrape_job.id)
    db.commit()
    updated = db.get(InstituteScrapeJob, scrape_job.id)

    assert mock_enrich.call_count == 1
    assert updated.leads_found == 1
    assert updated.status == "completed"
    new_lead = db.scalar(select(InstituteLead).where(InstituteLead.dedupe_key.like("listing:new.com%")))
    assert new_lead is not None
