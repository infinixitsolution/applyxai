import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.pagination import PageParams, page_params
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import User
from backend.app.schemas.billing import CheckoutIn, ConfirmIn
from backend.app.services import billing_service
from backend.app.services.payments import PaymentProvider, get_payment_provider

router = APIRouter(prefix="/billing", tags=["billing"])

MAX_WEBHOOK_BYTES = 256 * 1024


@router.get("", summary="Your plan, pending checkout, usage, and payments")
def billing_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db),
                     provider: PaymentProvider = Depends(get_payment_provider)):
    return ok(billing_service.overview(db, user, provider))


@router.get("/payments", summary="Paginated payment history for your account")
def billing_payments(status: str | None = None, params: PageParams = Depends(page_params),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(billing_service.list_user_payments(db, user.id, params, status=status))


@router.post("/checkout", summary="Start a subscription; returns what the provider's checkout needs")
def checkout(body: CheckoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
             provider: PaymentProvider = Depends(get_payment_provider),
             limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("20/hour", "billing-checkout", str(user.id))
    result = billing_service.checkout(db, user, provider, body.plan)
    db.commit()
    return ok(result)


@router.post("/confirm", summary="Verify a completed checkout with the provider")
def confirm(body: ConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
            provider: PaymentProvider = Depends(get_payment_provider),
            limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "billing-confirm", str(user.id))
    result = billing_service.confirm_checkout(db, user, provider, payment_id=body.payment_id,
                                              subscription_id=body.subscription_id, signature=body.signature)
    db.commit()
    return ok(result)


@router.get("/invoices")
def list_invoices(params: PageParams = Depends(page_params), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    from backend.app.services import gst_service
    return ok(gst_service.list_user_tax_invoices(db, user.id, params))


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.services import gst_service
    row = gst_service.get_user_invoice(db, user, invoice_id)
    return Response(
        content=gst_service.invoice_pdf_bytes(row),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{row.invoice_number}.pdf"'},
    )


@router.post("/cancel", summary="Cancel at the end of the current billing period")
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db),
           provider: PaymentProvider = Depends(get_payment_provider)):
    result = billing_service.cancel(db, user, provider)
    db.commit()
    return ok(result)


async def _raw_body(request: Request) -> bytes:
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_WEBHOOK_BYTES:
            raise AppError("PAYLOAD_TOO_LARGE", "Payload too large", 413)
    return body


@router.post("/webhook/{provider_name}", summary="Payment provider webhooks (signature-verified)",
             include_in_schema=False)
def webhook(provider_name: str, request: Request, body: bytes = Depends(_raw_body),
            db: Session = Depends(get_db), provider: PaymentProvider = Depends(get_payment_provider)):
    if provider_name != provider.name or provider.name == "null":
        raise AppError("NOT_FOUND", "Not found", 404)
    headers = {k.lower(): v for k, v in request.headers.items()}
    result = billing_service.handle_webhook(db, provider, headers, body)
    db.commit()
    return ok(result)
