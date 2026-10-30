"""Meta WhatsApp Cloud API send + inbound verify. Optional beside the unofficial bridge."""

from __future__ import annotations

import hashlib
import hmac
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.errors import AppError

logger = logging.getLogger("applyxai.whatsapp.cloud")

GRAPH = "https://graph.facebook.com/v21.0"

_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_VIDEO = {"video/mp4", "video/3gpp"}
_AUDIO = {"audio/aac", "audio/mp4", "audio/mpeg", "audio/amr", "audio/ogg", "audio/ogg; codecs=opus"}


def configured() -> bool:
    return bool((settings.WHATSAPP_CLOUD_TOKEN or "").strip() and (settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID or "").strip())


def send_text(phone: str, text: str) -> dict[str, Any]:
    if not configured():
        raise AppError(
            "WHATSAPP_CLOUD_NOT_CONFIGURED",
            "WhatsApp Cloud API is not configured. Set WHATSAPP_CLOUD_TOKEN and WHATSAPP_CLOUD_PHONE_NUMBER_ID, or use the bridge.",
            503,
        )
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) < 10:
        raise AppError("INVALID_PHONE", "Enter a valid WhatsApp number.", 422)
    url = f"{GRAPH}/{settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": digits,
        "type": "text",
        "text": {"body": (text or "")[:4096]},
    }
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_CLOUD_TOKEN}"},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp Cloud send failed: %s", type(exc).__name__)
        raise AppError("WHATSAPP_UNAVAILABLE", "WhatsApp Cloud API could not be reached.", 502) from exc
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        err = ((data.get("error") or {}).get("message")) or "WhatsApp Cloud rejected the message."
        raise AppError("WHATSAPP_REJECTED", str(err)[:300], 502)
    return {"ok": True, "provider": "cloud", "id": str(((data.get("messages") or [{}])[0].get("id") or ""))}


def media_kind(filename: str, mime: str | None = None) -> tuple[str, str]:
    """Return (whatsapp_type, mime) for Cloud media messages: image, video, audio, or document."""
    guessed, _ = mimetypes.guess_type(filename or "")
    content = (mime or guessed or "application/octet-stream").split(";")[0].strip().lower()
    if content in _IMAGE or content.startswith("image/"):
        return "image", content
    if content in _VIDEO or content.startswith("video/"):
        return "video", content
    if content in _AUDIO or content.startswith("audio/"):
        return "audio", content
    return "document", content or "application/octet-stream"


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_CLOUD_TOKEN}"},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp Cloud send failed: %s", type(exc).__name__)
        raise AppError("WHATSAPP_UNAVAILABLE", "WhatsApp Cloud API could not be reached.", 502) from exc
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        err = ((data.get("error") or {}).get("message")) or "WhatsApp Cloud rejected the message."
        raise AppError("WHATSAPP_REJECTED", str(err)[:300], 502)
    return data


def _upload_media(path: str, mime: str) -> str:
    url = f"{GRAPH}/{settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID}/media"
    try:
        with open(path, "rb") as fh:
            resp = httpx.post(
                url,
                data={"messaging_product": "whatsapp", "type": mime},
                files={"file": (os.path.basename(path), fh, mime)},
                headers={"Authorization": f"Bearer {settings.WHATSAPP_CLOUD_TOKEN}"},
                timeout=60,
            )
    except OSError as exc:
        raise AppError("WHATSAPP_REJECTED", "Could not read the attachment.", 422) from exc
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp Cloud media upload failed: %s", type(exc).__name__)
        raise AppError("WHATSAPP_UNAVAILABLE", "WhatsApp Cloud API could not be reached.", 502) from exc
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or not data.get("id"):
        err = ((data.get("error") or {}).get("message")) or "WhatsApp Cloud rejected the attachment."
        raise AppError("WHATSAPP_REJECTED", str(err)[:300], 502)
    return str(data["id"])


def send_media(phone: str, path: str, *, caption: str = "", filename: str = "") -> dict[str, Any]:
    if not configured():
        raise AppError(
            "WHATSAPP_CLOUD_NOT_CONFIGURED",
            "WhatsApp Cloud API is not configured. Set WHATSAPP_CLOUD_TOKEN and WHATSAPP_CLOUD_PHONE_NUMBER_ID, or use the bridge.",
            503,
        )
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) < 10:
        raise AppError("INVALID_PHONE", "Enter a valid WhatsApp number.", 422)
    if not path or not Path(path).is_file():
        raise AppError("VALIDATION_ERROR", "Attachment file is missing.", 422)
    fname = (filename or os.path.basename(path)).strip() or "file"
    wa_type, mime = media_kind(fname)
    media_id = _upload_media(path, mime)
    body: dict[str, Any] = {"id": media_id}
    if wa_type == "document":
        body["filename"] = fname[:240]
    if caption.strip() and wa_type in ("image", "video", "document"):
        body["caption"] = caption.strip()[:1024]
    data = _post_json(
        f"{GRAPH}/{settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID}/messages",
        {
            "messaging_product": "whatsapp",
            "to": digits,
            "type": wa_type,
            wa_type: body,
        },
    )
    return {
        "ok": True,
        "provider": "cloud",
        "id": str(((data.get("messages") or [{}])[0].get("id") or "")),
        "media_id": media_id,
        "media_type": wa_type,
    }


def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    expected = (settings.WHATSAPP_CLOUD_VERIFY_TOKEN or "").strip()
    if mode == "subscribe" and expected and token == expected:
        return challenge
    return None


def valid_signature(raw_body: bytes, header: str) -> bool:
    secret = (settings.WHATSAPP_CLOUD_APP_SECRET or "").strip()
    if not secret:
        return True
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


def parse_inbound(payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for msg in value.get("messages") or []:
                text = ((msg.get("text") or {}).get("body")) or ""
                from_wa = str(msg.get("from") or "")
                if from_wa:
                    out.append({
                        "from_wa": from_wa,
                        "body": str(text),
                        "message_id": str(msg.get("id") or ""),
                    })
    return out
