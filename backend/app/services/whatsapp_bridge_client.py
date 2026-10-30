"""HTTP client for the local WhatsApp Web bridge (QR session)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.errors import AppError

logger = logging.getLogger("applyxai.whatsapp.bridge")

_TIMEOUT = 15.0


def _base() -> str:
    return (settings.WHATSAPP_BRIDGE_URL or "").rstrip("/")


def get_status() -> dict[str, Any]:
    url = f"{_base()}/status"
    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp bridge unreachable: %s", exc)
        return {"status": "disconnected", "qr": None, "error": "Bridge not running. Start whatsapp-bridge."}


def _bridge_error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            err = body.get("error") or body.get("message")
            if err:
                return str(err)[:500]
    except Exception:
        pass
    text = (resp.text or "").strip()
    return text[:500] if text else "Could not send WhatsApp message via bridge."


def reset_client() -> dict[str, Any]:
    url = f"{_base()}/reset"
    try:
        resp = httpx.post(url, timeout=30.0)
        if resp.is_error:
            return {"ok": False, "error": _bridge_error_message(resp)}
        data = resp.json()
        return data if isinstance(data, dict) else {"ok": True}
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp reset failed: %s", exc)
        return {"ok": False, "error": "Could not reach WhatsApp bridge."}


def list_chats(*, limit: int = 100) -> dict[str, Any]:
    url = f"{_base()}/chats"
    try:
        resp = httpx.get(url, params={"limit": limit}, timeout=180.0)
        if resp.is_error:
            msg = _bridge_error_message(resp)
            if "Cannot GET /chats" in (resp.text or ""):
                msg = (
                    "WhatsApp bridge is outdated (no /chats). "
                    "Stop the old process and run: .\\scripts\\start_whatsapp_bridge.ps1"
                )
            return {"ok": False, "items": [], "error": msg}
        data = resp.json()
        return data if isinstance(data, dict) else {"ok": True, "items": []}
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp list chats failed: %s", exc)
        return {"ok": False, "items": [], "error": "Could not reach WhatsApp bridge."}


def fetch_chat_messages(chat_id: str, *, limit: int = 80) -> dict[str, Any]:
    from urllib.parse import quote

    cid = quote(chat_id, safe="")
    url = f"{_base()}/chats/{cid}/messages"
    try:
        resp = httpx.get(url, params={"limit": limit}, timeout=90.0)
        if resp.is_error:
            return {"ok": False, "items": [], "error": _bridge_error_message(resp)}
        data = resp.json()
        return data if isinstance(data, dict) else {"ok": True, "items": []}
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp fetch messages failed: %s", exc)
        return {"ok": False, "items": [], "error": "Could not reach WhatsApp bridge."}


def send_message(
    phone: str,
    text: str,
    *,
    media_path: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    url = f"{_base()}/send"
    payload: dict[str, Any] = {"phone": phone, "text": text}
    if media_path:
        payload["media_path"] = media_path
    if caption:
        payload["caption"] = caption
    try:
        resp = httpx.post(url, json=payload, timeout=60.0)
        if resp.is_error:
            msg = _bridge_error_message(resp)
            logger.warning("WhatsApp send failed %s: %s", resp.status_code, msg)
            raise AppError("WHATSAPP_SEND_FAILED", msg, resp.status_code if resp.status_code >= 400 else 502)
        data = resp.json()
        if isinstance(data, dict) and data.get("ok") is False:
            msg = str(data.get("error") or "Bridge rejected the send.")[:500]
            raise AppError("WHATSAPP_SEND_FAILED", msg, 502)
        return data if isinstance(data, dict) else {"ok": True}
    except AppError:
        raise
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp send failed: %s", exc)
        raise AppError("WHATSAPP_SEND_FAILED", "Could not reach WhatsApp bridge. Is it running?", 502) from exc
