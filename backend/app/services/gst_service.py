"""India GST helpers: validation, exclusive tax split, invoice numbering."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.core.pagination import PageParams, page_response, paginate
from backend.app.core.platform_defaults import DEFAULT_GST, PLATFORM_SETTINGS_KEY
from backend.app.models.billing import Payment, TaxInvoice
from backend.app.models.platform_settings import PlatformSettings
from backend.app.models.user import User

logger = logging.getLogger("applyxai.gst")

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_STATE_CODE_RE = re.compile(r"^\d{2}$")


def validate_gstin(gstin: str) -> str:
    value = (gstin or "").upper().strip()
    if not value:
        return ""
    if GSTIN_RE.match(value) is None:
        raise AppError("GSTIN_INVALID", "Enter a valid 15-character GSTIN.", 422)
    return value


def validate_pan(pan: str) -> str:
    value = (pan or "").upper().strip()
    if not value:
        return ""
    if PAN_RE.match(value) is None:
        raise AppError("PAN_INVALID", "Enter a valid PAN.", 422)
    return value


def normalize_state_code(code: str) -> str:
    raw = (code or "").strip()
    if not raw:
        return ""
    if not _STATE_CODE_RE.match(raw):
        raise AppError("STATE_CODE_INVALID", "State code must be a 2-digit GST state code.", 422)
    return raw


def normalize_gst_settings(raw: dict[str, Any] | None, *, strict: bool = False) -> dict[str, Any]:
    base = dict(DEFAULT_GST)
    if isinstance(raw, dict):
        base.update({k: v for k, v in raw.items() if v is not None})
    base["enabled"] = bool(base.get("enabled"))
    base["pricing_tax_exclusive"] = bool(base.get("pricing_tax_exclusive", True))
    try:
        base["rate_percent"] = float(base.get("rate_percent") or DEFAULT_GST["rate_percent"])
    except (TypeError, ValueError):
        base["rate_percent"] = float(DEFAULT_GST["rate_percent"])
    base["rate_percent"] = max(0.0, min(28.0, base["rate_percent"]))
    try:
        nxt = int(base.get("invoice_next_number") or 1)
    except (TypeError, ValueError):
        nxt = 1
    base["invoice_next_number"] = max(1, nxt)
    gstin_raw = str(base.get("gstin") or "").upper().strip()
    if gstin_raw:
        base["gstin"] = validate_gstin(gstin_raw) if strict else gstin_raw
    else:
        base["gstin"] = ""
    pan_raw = str(base.get("pan") or "").upper().strip()
    if pan_raw:
        base["pan"] = validate_pan(pan_raw) if strict else pan_raw
    else:
        base["pan"] = ""
    state_raw = str(base.get("state_code") or "").strip()
    if state_raw:
        try:
            base["state_code"] = normalize_state_code(state_raw)
        except AppError:
            if strict:
                raise
            base["state_code"] = state_raw
    else:
        base["state_code"] = ""
    for key in (
        "legal_name", "trade_name", "address_line1", "address_line2", "city", "state", "pin", "country",
        "sac_code", "invoice_prefix", "invoice_footer_note",
    ):
        base[key] = str(base.get(key) or "").strip()
    if not base["sac_code"]:
        base["sac_code"] = str(DEFAULT_GST["sac_code"])
    if not base["country"]:
        base["country"] = "India"
    if not base["invoice_prefix"]:
        base["invoice_prefix"] = str(DEFAULT_GST["invoice_prefix"])
    return base


def validate_gst_settings_for_enable(settings: dict[str, Any]) -> None:
    if not settings.get("enabled"):
        return
    if not settings.get("gstin"):
        raise AppError("GST_INCOMPLETE", "GSTIN is required when GST is enabled.", 422)
    if not (settings.get("legal_name") or "").strip():
        raise AppError("GST_INCOMPLETE", "Legal name is required when GST is enabled.", 422)
    if not settings.get("state_code"):
        raise AppError("GST_INCOMPLETE", "Supplier state code is required when GST is enabled.", 422)


def _split_tax_cents(tax_total: int) -> tuple[int, int, int]:
    """Return (cgst, sgst, igst) in paise."""
    half = tax_total // 2
    remainder = tax_total - half - half
    return half + remainder, half, 0


def compute_exclusive_totals(
    base_cents: int,
    rate_percent: float,
    supplier_state_code: str,
    buyer_state_code: str | None,
) -> dict[str, int]:
    """Pre-tax base + GST (exclusive pricing). Intra-state → CGST+SGST; else IGST."""
    taxable = max(0, int(base_cents))
    rate = max(0.0, float(rate_percent))
    tax_total = int(round(taxable * rate / 100.0))
    supplier = normalize_state_code(supplier_state_code) if supplier_state_code else ""
    buyer = normalize_state_code(buyer_state_code) if buyer_state_code else ""
    if supplier and buyer and supplier == buyer:
        cgst, sgst, igst = _split_tax_cents(tax_total)
    else:
        cgst, sgst, igst = 0, 0, tax_total
    total = taxable + tax_total
    return {
        "taxable_cents": taxable,
        "cgst_cents": cgst,
        "sgst_cents": sgst,
        "igst_cents": igst,
        "total_cents": total,
    }


def _platform_row(db: Session) -> PlatformSettings:
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    if row is None:
        row = PlatformSettings(key=PLATFORM_SETTINGS_KEY)
        db.add(row)
        db.flush()
    return row


def allocate_invoice_number(db: Session) -> str:
    row = _platform_row(db)
    gst = normalize_gst_settings(row.gst if isinstance(getattr(row, "gst", None), dict) else {})
    prefix = (gst.get("invoice_prefix") or "AXAI").strip() or "AXAI"
    number = int(gst.get("invoice_next_number") or 1)
    invoice_number = f"{prefix}-{number:05d}"
    gst["invoice_next_number"] = number + 1
    row.gst = gst
    db.flush()
    return invoice_number


def create_draft_invoice(
    db: Session,
    *,
    user_id: uuid.UUID,
    payment_id: uuid.UUID | None,
    supplier: dict[str, Any],
    buyer: dict[str, Any],
    line_items: list[dict[str, Any]],
    totals: dict[str, int],
    currency: str = "INR",
) -> TaxInvoice:
    """Persist a draft tax invoice."""
    invoice_number = allocate_invoice_number(db)
    row = TaxInvoice(
        user_id=user_id,
        payment_id=payment_id,
        invoice_number=invoice_number,
        status="draft",
        issued_at=None,
        supplier_json=supplier,
        buyer_json=buyer,
        line_items_json=line_items,
        taxable_cents=int(totals.get("taxable_cents") or 0),
        cgst_cents=int(totals.get("cgst_cents") or 0),
        sgst_cents=int(totals.get("sgst_cents") or 0),
        igst_cents=int(totals.get("igst_cents") or 0),
        total_cents=int(totals.get("total_cents") or 0),
        currency=(currency or "INR")[:3],
    )
    db.add(row)
    db.flush()
    return row


def tax_invoice_out(row: TaxInvoice) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "payment_id": str(row.payment_id) if row.payment_id else None,
        "user_id": str(row.user_id),
        "invoice_number": row.invoice_number,
        "status": row.status,
        "issued_at": row.issued_at.isoformat() if row.issued_at else None,
        "taxable_cents": row.taxable_cents,
        "cgst_cents": row.cgst_cents,
        "sgst_cents": row.sgst_cents,
        "igst_cents": row.igst_cents,
        "total_cents": row.total_cents,
        "currency": row.currency,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def get_effective_gst(db: Session) -> dict[str, Any]:
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_KEY)
    raw = row.gst if row and isinstance(getattr(row, "gst", None), dict) else {}
    return normalize_gst_settings(raw)


def list_tax_invoices(db: Session, params: PageParams) -> dict:
    stmt = select(TaxInvoice).order_by(TaxInvoice.created_at.desc())
    items, total = paginate(db, stmt, params)
    return page_response([tax_invoice_out(row) for row in items], total, params)


def gst_admin_view(stored: dict[str, Any]) -> dict[str, Any]:
    norm = normalize_gst_settings(stored)
    return {
        **norm,
        "configured": bool(norm.get("gstin")),
    }


def _rupees(cents: int) -> str:
    return f"{cents / 100:.2f}"


def invoice_pdf_bytes(row: TaxInvoice) -> bytes:
    """Minimal PDF 1.4 invoice (no extra library)."""
    supplier = row.supplier_json if isinstance(row.supplier_json, dict) else {}
    buyer = row.buyer_json if isinstance(row.buyer_json, dict) else {}
    lines = [
        f"Tax invoice {row.invoice_number}",
        f"Status: {row.status}",
        f"Supplier: {supplier.get('legal_name') or supplier.get('trade_name') or 'ApplyXAI'}",
        f"GSTIN: {supplier.get('gstin') or '-'}",
        f"Buyer: {buyer.get('name') or '-'}",
        f"Buyer email: {buyer.get('email') or '-'}",
        f"Taxable: {_rupees(row.taxable_cents)} {row.currency}",
        f"CGST: {_rupees(row.cgst_cents)}  SGST: {_rupees(row.sgst_cents)}  IGST: {_rupees(row.igst_cents)}",
        f"Total: {_rupees(row.total_cents)} {row.currency}",
        str(supplier.get("invoice_footer_note") or ""),
    ]
    text = "\n".join(line for line in lines if line)
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 11 Tf 50 750 Td 14 TL ({escaped}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    xref_positions = []
    out = bytearray(b"%PDF-1.4\n")
    for obj in objects:
        xref_positions.append(len(out))
        out.extend(obj)
    xref_start = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for pos in xref_positions:
        out.extend(f"{pos:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()
    )
    return bytes(out)


def finalize_invoice(db: Session, row: TaxInvoice) -> TaxInvoice:
    if row.status != "issued":
        row.status = "issued"
        row.issued_at = datetime.now(timezone.utc)
        db.flush()
    return row


def issue_for_payment(db: Session, payment: Payment) -> TaxInvoice | None:
    """Create and issue a GST invoice when GST is enabled and the payment is captured."""
    gst = get_effective_gst(db)
    if not gst.get("enabled"):
        return None
    status = (payment.status or "").lower()
    if status not in {"captured", "paid", "succeeded"}:
        return None
    existing = db.scalar(select(TaxInvoice).where(TaxInvoice.payment_id == payment.id))
    if existing is not None:
        return finalize_invoice(db, existing)

    user = db.get(User, payment.user_id)
    if user is None:
        return None
    buyer_state = ""
    buyer_gstin = ""
    buyer_name = " ".join(p for p in (user.first_name, user.last_name) if p) or user.email
    if payment.subscription_id:
        from backend.app.models import Institute, Subscription

        sub = db.get(Subscription, payment.subscription_id)
        if sub is not None and sub.institute_id:
            inst = db.get(Institute, sub.institute_id)
            if inst is not None:
                buyer_name = inst.name or buyer_name
                buyer_gstin = getattr(inst, "gstin", "") or ""
    amount = int(payment.amount_cents or 0)
    if gst.get("pricing_tax_exclusive"):
        totals = compute_exclusive_totals(amount, float(gst.get("rate_percent") or 18), gst.get("state_code") or "", buyer_state or None)
        taxable = totals["taxable_cents"]
    else:
        rate = max(0.0, float(gst.get("rate_percent") or 18))
        taxable = int(round(amount * 100.0 / (100.0 + rate))) if rate else amount
        totals = compute_exclusive_totals(taxable, rate, gst.get("state_code") or "", buyer_state or None)
        totals["total_cents"] = amount
    supplier = {
        "legal_name": gst.get("legal_name") or "ApplyXAI",
        "trade_name": gst.get("trade_name") or "",
        "gstin": gst.get("gstin") or "",
        "address_line1": gst.get("address_line1") or "",
        "city": gst.get("city") or "",
        "state": gst.get("state") or "",
        "state_code": gst.get("state_code") or "",
        "invoice_footer_note": gst.get("invoice_footer_note") or "",
    }
    buyer = {"name": buyer_name, "email": user.email, "gstin": buyer_gstin, "state_code": buyer_state}
    description = payment.description or "ApplyXAI subscription"
    row = create_draft_invoice(
        db,
        user_id=payment.user_id,
        payment_id=payment.id,
        supplier=supplier,
        buyer=buyer,
        line_items=[{"description": description, "amount_cents": taxable, "sac_code": gst.get("sac_code") or "998313"}],
        totals=totals,
        currency=payment.currency or "INR",
    )
    finalize_invoice(db, row)
    try:
        _email_invoice(db, user.email, row)
    except Exception:
        logger.exception("GST invoice email failed for %s", row.invoice_number)
    return row


def _email_invoice(db: Session, to: str, row: TaxInvoice) -> None:
    from backend.app.core.config import settings
    from backend.app.services.email_service import Email, get_email_sender

    origin = (settings.FRONTEND_URL or "").rstrip("/")
    link = f"{origin}/app/payment-history"
    body = (
        f"Tax invoice {row.invoice_number} for {_rupees(row.total_cents)} {row.currency}.\n\n"
        f"View payments: {link}\n"
    )
    pdf = invoice_pdf_bytes(row)
    get_email_sender(db).send(
        Email(
            to=to,
            subject=f"Tax invoice {row.invoice_number}",
            body=body,
            attachments=((f"{row.invoice_number}.pdf", pdf, "application/pdf"),),
        )
    )


def list_user_tax_invoices(db: Session, user_id: uuid.UUID, params: PageParams) -> dict:
    stmt = select(TaxInvoice).where(TaxInvoice.user_id == user_id).order_by(TaxInvoice.created_at.desc())
    items, total = paginate(db, stmt, params)
    return page_response([tax_invoice_out(row) for row in items], total, params)


def get_user_invoice(db: Session, user: User, invoice_id: uuid.UUID) -> TaxInvoice:
    row = db.get(TaxInvoice, invoice_id)
    if row is None or row.user_id != user.id:
        raise AppError("NOT_FOUND", "Invoice not found.", 404)
    return row

