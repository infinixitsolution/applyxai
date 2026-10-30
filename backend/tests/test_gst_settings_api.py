"""Admin GST settings API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.models import User
from backend.tests.conftest import csrf_headers

VALID_GSTIN = "29ABCDE1234F1Z5"


@pytest.fixture
def admin_client(app, db, make_user):
    client = make_user("gst-admin@example.com", client=TestClient(app, raise_server_exceptions=False))
    user = db.scalar(select(User).where(User.email == "gst-admin@example.com"))
    user.is_admin = True
    db.commit()
    return client


def test_settings_include_gst_defaults(admin_client):
    resp = admin_client.get("/api/admin/settings", headers=csrf_headers(admin_client))
    assert resp.status_code == 200
    gst = resp.json()["data"]["gst"]
    assert gst["enabled"] is False
    assert gst["sac_code"] == "998313"
    assert gst["pricing_tax_exclusive"] is True


def test_update_gst_roundtrip(admin_client):
    body = {
        "enabled": True,
        "legal_name": "ApplyXAI Technologies Pvt Ltd",
        "trade_name": "ApplyXAI",
        "address_line1": "123 MG Road",
        "address_line2": "",
        "city": "Bangalore",
        "state": "Karnataka",
        "state_code": "29",
        "pin": "560001",
        "country": "India",
        "gstin": VALID_GSTIN,
        "pan": "ABCDE1234F",
        "sac_code": "998313",
        "rate_percent": 18,
        "pricing_tax_exclusive": True,
        "invoice_prefix": "AXAI",
        "invoice_next_number": 100,
        "invoice_footer_note": "Thank you.",
    }
    put = admin_client.put("/api/admin/settings/gst", json=body, headers=csrf_headers(admin_client))
    assert put.status_code == 200, put.text
    gst = put.json()["data"]["gst"]
    assert gst["enabled"] is True
    assert gst["gstin"] == VALID_GSTIN
    assert gst["configured"] is True

    get = admin_client.get("/api/admin/settings", headers=csrf_headers(admin_client))
    assert get.json()["data"]["gst"]["legal_name"] == body["legal_name"]


def test_update_gst_rejects_invalid_gstin(admin_client):
    body = {
        "enabled": True,
        "legal_name": "Co",
        "trade_name": "",
        "address_line1": "",
        "address_line2": "",
        "city": "",
        "state": "",
        "state_code": "29",
        "pin": "",
        "country": "India",
        "gstin": "INVALID",
        "pan": "",
        "sac_code": "998313",
        "rate_percent": 18,
        "pricing_tax_exclusive": True,
        "invoice_prefix": "AXAI",
        "invoice_next_number": 1,
        "invoice_footer_note": "",
    }
    resp = admin_client.put("/api/admin/settings/gst", json=body, headers=csrf_headers(admin_client))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "GSTIN_INVALID"


def test_gst_preview_endpoint(admin_client):
    resp = admin_client.get(
        "/api/admin/settings/gst/preview",
        params={"base_cents": 10000, "buyer_state_code": "29"},
        headers=csrf_headers(admin_client),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["taxable_cents"] == 10000
    assert data["total_cents"] >= 10000


def test_tax_invoices_list_empty(admin_client):
    resp = admin_client.get(
        "/api/admin/billing/tax-invoices",
        params={"page": 1, "page_size": 5},
        headers=csrf_headers(admin_client),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []
