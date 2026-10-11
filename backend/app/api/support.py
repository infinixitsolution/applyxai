"""Candidate support chat with the admin team."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import User
from backend.app.schemas.live_interview import SupportMessageIn
from backend.app.services import support_service
from backend.app.services.payments import PaymentProvider, get_payment_provider

router = APIRouter(prefix="/support", tags=["support"])


@router.get("/thread", summary="This candidate's conversation with support")
def my_thread(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    thread = support_service.ensure_thread(db, user.id)
    db.commit()
    return ok({"thread": support_service.thread_out(db, thread, user), "messages": support_service.messages_for(db, thread)})


@router.post("/messages", summary="Send a support message")
def post_message(body: SupportMessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
                 limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("60/hour", "support-message", str(user.id))
    result = support_service.post_user_message(db, user, body.body)
    db.commit()
    return ok(result)


@router.post("/live-interview-request", summary="Ask for a live interview token and receive a payment link")
def request_token(user: User = Depends(get_current_user), db: Session = Depends(get_db),
                  provider: PaymentProvider = Depends(get_payment_provider),
                  limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("10/hour", "live-interview-request", str(user.id))
    result = support_service.request_live_interview(db, user, provider)
    db.commit()
    return ok(result)
