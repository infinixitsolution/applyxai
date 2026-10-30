"""Outreach automation tick (mocked services)."""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from backend.app.models.outreach import InstituteLead, InstituteLeadProfile, InstituteOutreachMessage
from backend.app.services import institute_outreach_automation_service, platform_settings_service


@pytest.fixture(autouse=True)
def automation_enabled(monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.OUTREACH_AUTOMATION_ENABLED", True)


@pytest.fixture
def campaign(db):
    return platform_settings_service.save_outreach_campaign(
        db,
        {
            "keywords": ["IT training"],
            "cities": ["Pune"],
            "sources": ["google"],
            "max_results": 5,
            "rotation_index": 0,
            "public_listing_attestation": True,
            "send_interval_min_sec": 60,
            "send_interval_max_sec": 120,
        },
    )


def test_tick_skips_incomplete_lead_after_complete(db, campaign):
    lead = InstituteLead(
        dedupe_key="host:auto-skip.example",
        display_name="Skip Me",
        status="discovered",
        completeness_score=40,
    )
    db.add(lead)
    db.flush()
    db.add(InstituteLeadProfile(lead_id=lead.id, payload={"name": "Skip Me"}))
    db.commit()

    with patch(
        "backend.app.services.institute_outreach_automation_service.institute_lead_complete_service.complete_lead_profile",
        return_value={"lead": lead, "completion": {}},
    ):
        result = institute_outreach_automation_service.run_automation_tick(db)

    db.refresh(lead)
    assert result.startswith("skipped_incomplete:")
    assert lead.status == "skipped_incomplete"


@patch("backend.app.services.institute_outreach_automation_service.institute_outreach_service.send_outreach")
@patch("backend.app.services.institute_outreach_automation_service.institute_outreach_service.generate_proposal")
def test_tick_generate_then_send(mock_generate, mock_send, db, campaign):
    lead = InstituteLead(
        dedupe_key="host:auto-send.example",
        display_name="Full Lead",
        status="enriched",
        completeness_score=100,
    )
    db.add(lead)
    db.flush()
    db.add(
        InstituteLeadProfile(
            lead_id=lead.id,
            payload={"name": "Full Lead", "emails": ["a@example.com"], "phones": ["+919999999999"]},
        )
    )
    db.commit()

    def _gen(_db, item):
        item.status = "proposal_ready"
        msg = InstituteOutreachMessage(lead_id=item.id, channel="email", status="draft", subject="Hi", body="Body")
        db.add(msg)
        db.add(InstituteOutreachMessage(lead_id=item.id, channel="whatsapp", status="draft", body="WA"))
        db.flush()
        return item

    mock_generate.side_effect = _gen
    mock_send.return_value = {"email": "a@example.com", "whatsapp": "+919999999999"}

    gen_result = institute_outreach_automation_service.run_automation_tick(db)
    assert gen_result.startswith("generate:")

    db.commit()
    lead = db.scalar(select(InstituteLead).where(InstituteLead.dedupe_key == "host:auto-send.example"))
    db.refresh(lead)
    assert lead.messages

    send_result = institute_outreach_automation_service.run_automation_tick(db)
    assert send_result.startswith("send:")
    mock_send.assert_called_once()
