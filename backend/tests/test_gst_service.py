"""GST calculation and invoice numbering."""

import uuid

import pytest
from sqlalchemy import select

from backend.app.core.platform_defaults import PLATFORM_SETTINGS_KEY
from backend.app.models import PlatformSettings, TaxInvoice, User
from backend.app.services import gst_service


def test_compute_exclusive_intra_state():
    totals = gst_service.compute_exclusive_totals(10_000, 18.0, "29", "29")
    assert totals["taxable_cents"] == 10_000
    assert totals["cgst_cents"] + totals["sgst_cents"] == 1800
    assert totals["igst_cents"] == 0
    assert totals["total_cents"] == 11_800


def test_compute_exclusive_inter_state():
    totals = gst_service.compute_exclusive_totals(10_000, 18.0, "29", "27")
    assert totals["igst_cents"] == 1800
    assert totals["cgst_cents"] == 0
    assert totals["sgst_cents"] == 0
    assert totals["total_cents"] == 11_800


def test_validate_gstin_rejects_bad():
    with pytest.raises(Exception):
        gst_service.validate_gstin("not-a-gstin")


def test_allocate_invoice_number_increments(db):
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
    row.gst = {
        "invoice_prefix": "TST",
        "invoice_next_number": 42,
        "rate_percent": 18,
    }
    db.commit()
    num = gst_service.allocate_invoice_number(db)
    assert num == "TST-00042"
    db.refresh(row)
    assert row.gst["invoice_next_number"] == 43


def test_create_draft_invoice(db):
    user = db.scalar(select(User).limit(1))
    if user is None:
        user = User(email="gst-inv@example.com", password_hash="x", is_verified=True)
        db.add(user)
        db.flush()
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
    row.gst = {"invoice_prefix": "DR", "invoice_next_number": 1, "rate_percent": 18, "state_code": "29"}
    db.commit()
    totals = gst_service.compute_exclusive_totals(5000, 18, "29", "29")
    inv = gst_service.create_draft_invoice(
        db,
        user_id=user.id,
        payment_id=None,
        supplier={"legal_name": "ApplyXAI"},
        buyer={"name": "Test"},
        line_items=[{"description": "Pro plan", "amount_cents": 5000}],
        totals=totals,
    )
    db.commit()
    loaded = db.get(TaxInvoice, inv.id)
    assert loaded is not None
    assert loaded.status == "draft"
    assert loaded.invoice_number.startswith("DR-")
