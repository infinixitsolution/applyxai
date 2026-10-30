"""Admin institute outreach API (mocked Firecrawl + WhatsApp bridge)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.models import User
from backend.app.models.outreach import InstituteLead, InstituteLeadChatMessage, InstituteLeadProfile, InstituteOutreachMessage
from backend.tests.conftest import csrf_headers


@pytest.fixture
def admin(app, db, make_user):
    client = make_user("outreach-admin@example.com", client=TestClient(app, raise_server_exceptions=False))
    user = db.scalar(select(User).where(User.email == "outreach-admin@example.com"))
    user.is_admin = True
    db.commit()
    return client


def post(client, path, body):
    return client.post(f"/api/admin/outreach{path}", json=body, headers=csrf_headers(client))


def get(client, path):
    return client.get(f"/api/admin/outreach{path}", headers=csrf_headers(client))


def test_scrape_job_requires_firecrawl(admin, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_firecrawl_api_key",
        lambda _db: "",
    )
    resp = post(
        admin,
        "/scrape-jobs",
        {
            "query": "coaching centre",
            "location": "Pune",
            "sources": ["google"],
            "max_results": 5,
            "public_listing_attestation": True,
        },
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "FIRECRAWL_NOT_CONFIGURED"


def test_scrape_job_requires_attestation(admin):
    resp = post(
        admin,
        "/scrape-jobs",
        {
            "query": "coaching centre",
            "location": "Pune",
            "sources": ["google"],
            "max_results": 5,
            "public_listing_attestation": False,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ATTESTATION_REQUIRED"


@patch("backend.app.services.institute_outreach_service.dispatch_scrape_job")
def test_start_scrape_job(mock_dispatch, admin, monkeypatch):
    mock_dispatch.side_effect = lambda db_, job: job
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_firecrawl_api_key",
        lambda _db: "fc-test",
    )
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_ai",
        lambda _db: type("Ai", (), {"feature_on": lambda _s, _f: True})(),
    )

    resp = post(
        admin,
        "/scrape-jobs",
        {
            "query": "IT training",
            "location": "Hyderabad",
            "sources": ["google"],
            "max_results": 3,
            "public_listing_attestation": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["query"] == "IT training"


def test_list_leads_empty(admin):
    resp = get(admin, "/leads")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_leads_dashboard_stats(admin, db):
    db.add(
        InstituteLead(
            dedupe_key="stats:1",
            display_name="A",
            status="completing_profile",
            completeness_score=10,
        )
    )
    db.add(
        InstituteLead(
            dedupe_key="stats:2",
            display_name="B",
            status="enriched",
            completeness_score=100,
        )
    )
    db.commit()

    resp = get(admin, "/leads/stats")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["profile_completing"] == 1
    assert data["profile_completion_pending"] == 1
    assert data["completeness_full"] == 1
    assert data["enriched"] == 1


@patch("backend.app.services.institute_outreach_service.dispatch_bulk_lead_enrichment")
def test_bulk_import_creates_and_queues_enrichment(mock_dispatch, admin, db, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_firecrawl_api_key",
        lambda _db: "fc-test",
    )
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_ai",
        lambda _db: type("Ai", (), {"feature_on": lambda _s, _f: True})(),
    )

    resp = post(
        admin,
        "/leads/bulk-import",
        {
            "contacts": "Alpha Coaching, partner@alpha.in\n9876543210",
            "enrich": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 2
    assert data["enrich_queued"] == 2
    assert len(data["items"]) == 2
    assert all(item.get("enrich_queued") for item in data["items"])
    mock_dispatch.assert_called_once()
    queued_ids = mock_dispatch.call_args[0][0]
    assert len(queued_ids) == 2

    lead = db.scalar(select(InstituteLead).where(InstituteLead.dedupe_key == "manual:email:partner@alpha.in"))
    assert lead is not None
    assert lead.source_platform == "manual"


@patch("backend.app.services.institute_lead_complete_service.complete_lead_profile")
def test_bulk_complete_profile_action(mock_complete, admin, db, monkeypatch):
    mock_complete.side_effect = lambda db_, lead: {
        "lead": lead,
        "completion": {"score_before": 10, "score_after": 60, "searches_run": 1, "search_hits": 1,
                       "urls_scraped": 1, "urls_skipped": 0, "snippets_used": 1, "hints": []},
    }
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_firecrawl_api_key",
        lambda _db: "fc-test",
    )
    monkeypatch.setattr(
        "backend.app.services.institute_scrape_service.get_effective_ai",
        lambda _db: type("Ai", (), {"feature_on": lambda _s, _f: True})(),
    )
    lead = InstituteLead(dedupe_key="host:bulk.com", display_name="Bulk Co", status="discovered", completeness_score=5)
    db.add(lead)
    db.flush()
    db.add(InstituteLeadProfile(lead_id=lead.id, payload={"name": "Bulk Co", "emails": ["x@bulk.com"]}))
    db.commit()

    resp = post(admin, "/leads/bulk-action", {"lead_ids": [str(lead.id)], "action": "complete"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["succeeded"] == 1
    assert data["action"] == "complete"


def test_bulk_import_skips_duplicate(admin, db):
    db.add(
        InstituteLead(
            dedupe_key="manual:email:dup@x.com",
            display_name="Dup",
            source_platform="manual",
            status="discovered",
        )
    )
    db.commit()

    resp = post(admin, "/leads/bulk-import", {"contacts": "dup@x.com", "enrich": False})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 0
    assert data["existing"] == 1


@patch("backend.app.services.whatsapp_bridge_client.get_status")
def test_whatsapp_status_proxy(mock_status, admin, db):
    mock_status.return_value = {"status": "qr", "qr": "data:image/png;base64,abc"}
    resp = get(admin, "/whatsapp/status")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "qr"


@patch("backend.app.services.whatsapp_bridge_client.send_message")
@patch("backend.app.services.whatsapp_bridge_client.get_status")
def test_whatsapp_test_send(mock_status, mock_send, admin):
    mock_status.return_value = {"status": "connected", "ready": True}
    mock_send.return_value = {"ok": True, "id": "msg-1"}
    resp = post(
        admin,
        "/whatsapp/test-send",
        {"phone": "+919876543210", "text": "ApplyXAI test"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sent"] is True
    mock_send.assert_called_once()


@patch("backend.app.services.institute_lead_complete_service.complete_lead_profile")
def test_complete_lead_profile(mock_complete, admin, db):
    lead = InstituteLead(
        dedupe_key="host:complete-test.com",
        display_name="Complete Me Institute",
        status="discovered",
        source_url="https://complete-test.com",
    )
    db.add(lead)
    db.flush()
    db.add(InstituteLeadProfile(lead_id=lead.id, payload={"name": "Complete Me Institute"}))
    db.commit()

    def _done(_db, item):
        item.completeness_score = 75
        item.status = "enriched"
        return {
            "lead": item,
            "completion": {"score_before": 30, "score_after": 75, "searches_run": 2, "hints": []},
        }

    mock_complete.side_effect = _done

    resp = admin.post(
        f"/api/admin/outreach/leads/{lead.id}/complete-profile",
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    mock_complete.assert_called_once()


@patch("backend.app.services.institute_proposal_service.generate_proposals")
def test_generate_proposal(mock_gen, admin, db):
    lead = InstituteLead(
        dedupe_key="host:example.com",
        display_name="Example Institute",
        status="enriched",
        completeness_score=100,
    )
    db.add(lead)
    db.flush()
    db.add(
        InstituteLeadProfile(
            lead_id=lead.id,
            payload={
                "name": "Example Institute",
                "emails": ["a@b.com"],
                "phones": ["+919999999999"],
                "website": "https://example.com",
                "description": "Test institute",
                "address": {"city": "Pune", "line": "Main road"},
                "programs": ["Java"],
            },
        )
    )
    db.commit()

    mock_gen.return_value = ("Subject", "Body", "<p>Body</p>", "WA text")

    resp = admin.post(
        f"/api/admin/outreach/leads/{lead.id}/generate-proposal",
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "proposal_ready"
    assert len(body["messages"]) >= 1


def test_generate_proposal_requires_full_profile(admin, db):
    lead = InstituteLead(
        dedupe_key="host:partial.com",
        display_name="Partial",
        status="enriched",
        completeness_score=50,
    )
    db.add(lead)
    db.flush()
    db.add(InstituteLeadProfile(lead_id=lead.id, payload={"name": "Partial", "emails": ["a@b.com"]}))
    db.commit()

    resp = admin.post(
        f"/api/admin/outreach/leads/{lead.id}/generate-proposal",
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "PROFILE_INCOMPLETE"


def test_whatsapp_inbound_chat(app, db, monkeypatch):
    monkeypatch.setattr("backend.app.core.config.settings.WHATSAPP_BRIDGE_SECRET", "test-bridge-secret")
    lead = InstituteLead(
        dedupe_key="host:chat.com",
        display_name="Chat Institute",
        status="sent",
        completeness_score=100,
        whatsapp_phone="+919876543210",
    )
    db.add(lead)
    db.commit()

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/internal/outreach/whatsapp/inbound",
        json={"from": "919876543210@c.us", "body": "We are interested", "message_id": "wa-msg-1"},
        headers={"X-WhatsApp-Bridge-Secret": "test-bridge-secret"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["accepted"] is True
    db.refresh(lead)
    assert lead.status == "replied"
    rows = db.scalars(
        select(InstituteLeadChatMessage).where(InstituteLeadChatMessage.lead_id == lead.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].direction == "inbound"
    assert rows[0].body == "We are interested"


@patch("backend.app.services.whatsapp_bridge_client.send_message")
@patch("backend.app.services.whatsapp_bridge_client.get_status")
def test_admin_lead_chat_send(mock_status, mock_send, admin, db):
    mock_status.return_value = {"status": "connected", "ready": True}
    mock_send.return_value = {"id": "sent-1"}
    lead = InstituteLead(
        dedupe_key="host:reply.com",
        display_name="Reply Institute",
        status="replied",
        completeness_score=100,
        whatsapp_phone="+919876543210",
    )
    db.add(lead)
    db.commit()

    resp = post(admin, f"/leads/{lead.id}/chat", {"channel": "whatsapp", "text": "Thanks — let's talk Monday"})
    assert resp.status_code == 200, resp.text
    msg = resp.json()["data"]["message"]
    assert msg["direction"] == "outbound"
    assert "Monday" in msg["body"]
    mock_send.assert_called_once()


@patch("backend.app.services.whatsapp_bridge_client.send_message")
@patch("backend.app.services.whatsapp_bridge_client.get_status")
def test_admin_lead_chat_send_attachment(mock_status, mock_send, admin, db):
    mock_status.return_value = {"status": "connected", "ready": True}
    mock_send.return_value = {"id": "sent-2"}
    lead = InstituteLead(
        dedupe_key="host:attach.com",
        display_name="Attach Institute",
        status="replied",
        completeness_score=100,
        whatsapp_phone="+919876543211",
    )
    db.add(lead)
    db.commit()

    resp = admin.post(
        f"/api/admin/outreach/leads/{lead.id}/chat/attachment",
        data={"text": "Please see the brochure"},
        files={"file": ("brochure.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["data"]["message"]
    assert msg["direction"] == "outbound"
    assert "brochure" in msg["body"].lower()
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs.get("media_path")


def test_proposal_image_upload(admin, tmp_path, monkeypatch):
    from backend.app.services import institute_proposal_image_service

    pub = tmp_path / "public" / "outreach" / "campus-partnership-proposal.jpg"
    assets = tmp_path / "assets" / "outreach" / "campus-partnership-proposal.jpg"
    monkeypatch.setattr(
        institute_proposal_image_service,
        "_destinations",
        lambda: [assets, pub],
    )
    monkeypatch.setattr(
        "backend.app.services.institute_proposal_image_service.proposal_image_public_url",
        lambda: "/outreach/campus-partnership-proposal.jpg",
    )

    info = get(admin, "/proposal-image")
    assert info.status_code == 200
    assert info.json()["data"]["url"] == "/outreach/campus-partnership-proposal.jpg"

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    resp = admin.post(
        "/api/admin/outreach/proposal-image",
        files={"file": ("banner.png", png_bytes, "image/png")},
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    assert pub.is_file() and assets.is_file()
    assert resp.json()["data"]["url"] == "/outreach/campus-partnership-proposal.jpg"


def test_whatsapp_recent_sends(admin, db):
    from datetime import datetime, timezone

    lead = InstituteLead(
        dedupe_key="host:recent-wa.com",
        display_name="Recent WA Lead",
        status="replied",
        completeness_score=100,
    )
    db.add(lead)
    db.flush()
    sent_at = datetime.now(timezone.utc)
    db.add(
        InstituteOutreachMessage(
            lead_id=lead.id,
            channel="email",
            subject="Hi",
            body="Email body",
            status="sent",
            sent_at=sent_at,
        )
    )
    db.add(
        InstituteOutreachMessage(
            lead_id=lead.id,
            channel="whatsapp",
            body="Hello from outreach proposal",
            status="sent",
            sent_at=sent_at,
        )
    )
    db.commit()

    resp = get(admin, "/whatsapp/recent-sends?limit=5")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) >= 1
    wa = next(i for i in items if i["lead_id"] == str(lead.id))
    assert "Hello from outreach" in wa["preview"]
    assert wa["name"] == "Recent WA Lead"


@patch("backend.app.services.whatsapp_bridge_client.fetch_chat_messages")
@patch("backend.app.services.whatsapp_bridge_client.list_chats")
@patch("backend.app.services.whatsapp_bridge_client.get_status")
def test_whatsapp_sync_chats(mock_status, mock_list, mock_msgs, admin, db):
    mock_status.return_value = {"status": "connected", "ready": True}
    mock_list.return_value = {
        "ok": True,
        "total": 1,
        "items": [
            {
                "id": "919988776655@c.us",
                "name": "Sync Contact",
                "phone": "919988776655",
                "last_message": {
                    "id": "wa-sync-1",
                    "body": "Hello from WhatsApp",
                    "from_me": False,
                    "timestamp": 1_700_000_000,
                },
            }
        ],
    }
    mock_msgs.return_value = {"ok": True, "items": []}

    resp = admin.post("/api/admin/outreach/whatsapp/sync-chats?limit=10", headers=csrf_headers(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["synced"] is True
    assert data["messages_imported"] >= 1
    lead = db.scalar(select(InstituteLead).where(InstituteLead.dedupe_key == "wa:919988776655"))
    assert lead is not None
    assert lead.display_name == "Sync Contact"


def test_whatsapp_chat_threads(admin, db):
    from datetime import datetime, timedelta, timezone

    lead = InstituteLead(
        dedupe_key="host:threads.com",
        display_name="Thread Lead",
        status="replied",
        completeness_score=100,
        whatsapp_phone="+919111111111",
    )
    db.add(lead)
    db.flush()
    t0 = datetime.now(timezone.utc)
    db.add(
        InstituteLeadChatMessage(
            lead_id=lead.id,
            channel="whatsapp",
            direction="outbound",
            body="Proposal sent",
            external_id="out:1",
            created_at=t0,
            updated_at=t0,
        )
    )
    t1 = t0 + timedelta(seconds=1)
    db.add(
        InstituteLeadChatMessage(
            lead_id=lead.id,
            channel="whatsapp",
            direction="inbound",
            body="We are interested",
            external_id="in:1",
            created_at=t1,
            updated_at=t1,
        )
    )
    db.commit()

    resp = get(admin, "/whatsapp/chat-threads?page=1&page_size=10")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    row = next(i for i in items if i["lead_id"] == str(lead.id))
    assert row["last_message"]["direction"] == "inbound"
    assert row["message_count"] == 2


def _set_whatsapp_cloud(db):
    from backend.app.core.platform_defaults import PLATFORM_SETTINGS_KEY
    from backend.app.models import PlatformSettings
    from backend.app.services.platform_settings_service import invalidate_caches

    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
        db.flush()
    outreach = dict(row.outreach or {})
    outreach["whatsapp_provider"] = "cloud"
    row.outreach = outreach
    db.commit()
    invalidate_caches()


@patch("backend.app.services.whatsapp_cloud_client.send_media")
@patch("backend.app.services.whatsapp_cloud_client.configured", return_value=True)
def test_admin_lead_chat_cloud_attachment(mock_configured, mock_send, admin, db):
    mock_send.return_value = {"ok": True, "provider": "cloud", "id": "wamid.cloud-1", "media_id": "media-1", "media_type": "document"}
    _set_whatsapp_cloud(db)
    lead = InstituteLead(
        dedupe_key="host:cloud-attach.com",
        display_name="Cloud Attach Institute",
        status="replied",
        completeness_score=100,
        whatsapp_phone="+919876543299",
    )
    db.add(lead)
    db.commit()

    resp = admin.post(
        f"/api/admin/outreach/leads/{lead.id}/chat/attachment",
        data={"text": "Please see the brochure"},
        files={"file": ("brochure.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["data"]["message"]
    assert msg["direction"] == "outbound"
    assert "brochure" in msg["body"].lower()
    mock_send.assert_called_once()
    assert mock_send.call_args.args[1]
    assert mock_send.call_args.kwargs.get("filename") == "brochure.pdf"


@patch("backend.app.services.whatsapp_cloud_client.send_text")
@patch("backend.app.services.whatsapp_cloud_client.configured", return_value=True)
def test_admin_lead_chat_cloud_text_records_outbound(mock_configured, mock_send, admin, db):
    mock_send.return_value = {"ok": True, "provider": "cloud", "id": "wamid.cloud-2"}
    _set_whatsapp_cloud(db)
    lead = InstituteLead(
        dedupe_key="host:cloud-text.com",
        display_name="Cloud Text Institute",
        status="replied",
        completeness_score=100,
        whatsapp_phone="+919876543288",
    )
    db.add(lead)
    db.commit()

    resp = post(admin, f"/leads/{lead.id}/chat", {"channel": "whatsapp", "text": "Cloud hello"})
    assert resp.status_code == 200, resp.text
    msg = resp.json()["data"]["message"]
    assert msg["direction"] == "outbound"
    assert "Cloud hello" in msg["body"]
    mock_send.assert_called_once()
