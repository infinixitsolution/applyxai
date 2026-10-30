"""Internal hooks (WhatsApp bridge → API). No session; protected by shared secret."""

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.services import institute_outreach_chat_service, whatsapp_cloud_client

router = APIRouter(prefix="/internal/outreach", tags=["internal"])


class WhatsappInboundIn(BaseModel):
    from_wa: str = Field(validation_alias=AliasChoices("from", "from_wa"))
    body: str = ""
    message_id: str | None = None
    display_name: str = Field(default="", max_length=190)
    chat_id: str = Field(default="", max_length=190)


@router.post("/whatsapp/inbound")
def whatsapp_inbound(
    body: WhatsappInboundIn,
    db: Session = Depends(get_db),
    secret: str = Header(default="", alias="X-WhatsApp-Bridge-Secret"),
):
    institute_outreach_chat_service.verify_bridge_secret(secret)
    result = institute_outreach_chat_service.ingest_inbound(
        db,
        from_wa=body.from_wa,
        body=body.body,
        message_id=body.message_id,
        display_name=body.display_name,
        chat_id=body.chat_id,
    )
    db.commit()
    return ok({"accepted": result is not None, "result": result})


@router.get("/whatsapp-cloud")
def whatsapp_cloud_verify(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    verified = whatsapp_cloud_client.verify_webhook(mode, token, challenge)
    if verified is None:
        raise AppError("FORBIDDEN", "Invalid WhatsApp Cloud verify token.", 403)
    return PlainTextResponse(verified)


@router.post("/whatsapp-cloud")
async def whatsapp_cloud_inbound(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not whatsapp_cloud_client.valid_signature(raw, sig):
        raise AppError("INVALID_SIGNATURE", "Invalid WhatsApp Cloud signature.", 400)
    try:
        import json
        payload = json.loads(raw.decode() or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    accepted = 0
    for msg in whatsapp_cloud_client.parse_inbound(payload):
        result = institute_outreach_chat_service.ingest_inbound(
            db,
            from_wa=msg["from_wa"],
            body=msg["body"],
            message_id=msg.get("message_id"),
        )
        if result is not None:
            accepted += 1
    db.commit()
    return ok({"accepted": accepted})
