"""ElevenLabs TTS and ConvAI agent metadata for mock interview voice."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError

logger = logging.getLogger("applyxai.elevenlabs")

_BASE = "https://api.elevenlabs.io/v1"
_AGENT_VOICE_CACHE: dict[str, tuple[str, float]] = {}
_AGENT_VOICE_TTL_SEC = 3600.0


def _normalize_api_key(value: str) -> str:
    key = (value or "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
        key = key[1:-1].strip()
    return key


def resolve_api_key(db: Session | None = None, *, override: str | None = None) -> str:
    if override and override.strip():
        return _normalize_api_key(override)
    from backend.app.services.platform_settings_service import get_effective_elevenlabs_api_key

    key = get_effective_elevenlabs_api_key(db)
    if not key:
        raise AppError("ELEVENLABS_DISABLED", "ElevenLabs API key is not configured.", 503)
    return key


def _elevenlabs_error_detail(payload: Any) -> str:
    """Human-readable message from ElevenLabs JSON error bodies."""
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "error", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _elevenlabs_error_detail(value)
            if nested:
                return nested
    return ""


def _verify_error_message(resp: httpx.Response) -> str:
    detail = ""
    try:
        detail = _elevenlabs_error_detail(resp.json())
    except Exception:
        detail = (resp.text or "").strip()[:200]
    status = resp.status_code
    if status == 401:
        hint = (
            "Create a key at https://elevenlabs.io/app/settings/api-keys (ElevenLabs only — not OpenAI), "
            "paste it in the ElevenLabs API key field, Save on the Platform AI card, then Test again."
        )
        if detail:
            return f"ElevenLabs: {detail}. {hint}"
        return f"ElevenLabs rejected this API key. {hint}"
    if status == 403:
        base = "ElevenLabs denied access for this API key. Check your ElevenLabs plan and key permissions."
        return f"{base} {detail}".strip() if detail else base
    if detail:
        return f"ElevenLabs API check failed (HTTP {status}): {detail}"
    return f"ElevenLabs API check failed (HTTP {status})."


def verify_credentials(*, api_key: str | None = None, db: Session | None = None) -> dict:
    key = resolve_api_key(db, override=api_key)
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{_BASE}/user", headers={"xi-api-key": key})
    if resp.status_code >= 400:
        raise AppError(
            "ELEVENLABS_ERROR",
            _verify_error_message(resp),
            502,
        )
    data = resp.json() if resp.content else {}
    sub = data.get("subscription") if isinstance(data, dict) else {}
    tier = sub.get("tier") if isinstance(sub, dict) else None
    return {
        "ok": True,
        "message": "ElevenLabs API key verified.",
        "tier": tier,
    }


def get_agent_voice_id(agent_id: str, db: Session | None = None) -> str:
    """Resolve TTS voice_id from a ConvAI agent (cached)."""
    aid = (agent_id or "").strip()
    if not aid:
        raise AppError("VALIDATION_ERROR", "ElevenLabs agent id is required.", 422)
    now = time.monotonic()
    cached = _AGENT_VOICE_CACHE.get(aid)
    if cached and now - cached[1] < _AGENT_VOICE_TTL_SEC:
        return cached[0]

    headers = {"xi-api-key": resolve_api_key(db)}
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{_BASE}/convai/agents/{aid}", headers=headers)
    if resp.status_code == 404:
        raise AppError("ELEVENLABS_NOT_FOUND", "ElevenLabs agent was not found.", 404)
    if resp.status_code >= 400:
        raise AppError("ELEVENLABS_ERROR", f"ElevenLabs agent lookup failed ({resp.status_code}).", 502)
    data = resp.json()
    voice_id = _voice_id_from_agent_payload(data)
    if not voice_id:
        raise AppError("ELEVENLABS_ERROR", "ElevenLabs agent has no TTS voice configured.", 502)
    _AGENT_VOICE_CACHE[aid] = (voice_id, now)
    return voice_id


def _voice_id_from_agent_payload(data: dict[str, Any]) -> str:
    for key in ("voice_id",):
        if isinstance(data.get(key), str) and data[key].strip():
            return data[key].strip()
    conversation = data.get("conversation_config")
    if isinstance(conversation, dict):
        tts = conversation.get("tts")
        if isinstance(tts, dict):
            vid = tts.get("voice_id")
            if isinstance(vid, str) and vid.strip():
                return vid.strip()
    agent = data.get("agent")
    if isinstance(agent, dict):
        return _voice_id_from_agent_payload(agent)
    return ""


def synthesize_speech(
    text: str,
    *,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    db: Session | None = None,
) -> bytes:
    prepared = (text or "").strip()
    if not prepared:
        return b""
    vid = (voice_id or "").strip()
    if not vid:
        raise AppError("VALIDATION_ERROR", "ElevenLabs voice_id is required.", 422)
    model = (model_id or "eleven_multilingual_v2").strip()
    headers = {
        "xi-api-key": resolve_api_key(db),
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": prepared[:4096],
        "model_id": model,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{_BASE}/text-to-speech/{vid}", headers=headers, json=body)
    if resp.status_code >= 400:
        logger.warning("ElevenLabs TTS failed status=%s body=%s", resp.status_code, resp.text[:200])
        raise AppError("ELEVENLABS_ERROR", f"ElevenLabs TTS failed ({resp.status_code}).", 502)
    return resp.content
