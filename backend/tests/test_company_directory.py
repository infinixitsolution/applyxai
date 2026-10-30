from unittest.mock import patch

import pytest

from backend.app.services import company_directory_service


@pytest.fixture
def db_session(db):
    return db


def test_enrich_merges_contacts_from_search_and_scrape(db_session):
    profile = company_directory_service.get_or_create_profile(db_session, "Jobgether")
    db_session.commit()

    hits = [{"url": "https://example.com/careers", "title": "Careers", "description": "Contact hr@jobgether.com for roles."}]
    scrape = {"markdown": "Recruiter Jane Doe · jane.doe@jobgether.com · +1 555 010 9999"}

    with patch.object(company_directory_service.firecrawl_client, "search_web", return_value=hits):
        with patch.object(company_directory_service, "_firecrawl_ready", return_value=True):
            with patch.object(company_directory_service.firecrawl_client, "scrape_url", return_value=scrape):
                company_directory_service.enrich_profile(db_session, "Jobgether")
    db_session.commit()

    assert profile.status == "ready"
    emails = {c.get("email") for c in profile.contacts}
    assert "hr@jobgether.com" in emails or "jane.doe@jobgether.com" in emails
    assert profile.source_pages
