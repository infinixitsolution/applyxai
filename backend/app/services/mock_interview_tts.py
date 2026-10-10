"""Text-to-speech profile for the mock interview AI interviewer."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.core.platform_defaults import DEFAULT_AI
from backend.app.services import ai_service

logger = logging.getLogger("applyxai.mock_interview.tts")

_FEATURE = "mock_interview"

# OpenAI: shimmer / coral read as feminine; gpt-4o-mini-tts supports `instructions` for accent and pace.
INTERVIEWER_VOICE_DEFAULTS: dict[str, Any] = {
    "model": "gpt-4o-mini-tts",
    "fallback_model": "tts-1-hd",
    "last_resort_model": "tts-1",
    "voice": "shimmer",
    "speed": 0.92,
    "instructions": (
        "You are an adult Indian woman conducting a professional job interview. "
        "Use natural Indian English as spoken in Indian tech and business settings (clear, neutral metro accent—not exaggerated). "
        "Sound warm, confident, and respectful. Speak at a measured pace with brief pauses at commas and before the main question. "
        "Pronounce names, company names, and technical terms carefully."
    ),
}


def _merge_voice_settings(db: Session | None) -> dict[str, Any]:
    base = dict(DEFAULT_AI.get("mock_interview_voice") or INTERVIEWER_VOICE_DEFAULTS)
    for key, value in INTERVIEWER_VOICE_DEFAULTS.items():
        base.setdefault(key, value)
    if db is not None:
        from backend.app.services.platform_settings_service import _row

        overlay = (_row(db).ai or {}).get("mock_interview_voice")
        if isinstance(overlay, dict):
            for key, value in overlay.items():
                if value is not None and value != "":
                    base[key] = value
    return base


def prepare_interviewer_speech_text(text: str) -> str:
    """Light cleanup so TTS reads interview lines naturally."""
    snippet = (text or "").strip()
    snippet = re.sub(r"\s+", " ", snippet)
    snippet = snippet.replace("&", " and ")
    return snippet[:4096]


def synthesize_interviewer_speech(db: Session | None, text: str) -> bytes:
    cfg = _merge_voice_settings(db)
    prepared = prepare_interviewer_speech_text(text)
    if not prepared:
        return b""

    attempts: list[dict[str, Any]] = [
        {
            "model": cfg["model"],
            "voice": cfg["voice"],
            "speed": cfg.get("speed"),
            "instructions": cfg.get("instructions"),
        },
        {
            "model": cfg.get("fallback_model") or "tts-1-hd",
            "voice": cfg["voice"],
            "speed": cfg.get("speed"),
            "instructions": None,
        },
        {
            "model": cfg.get("last_resort_model") or "tts-1",
            "voice": cfg["voice"],
            "speed": None,
            "instructions": None,
        },
    ]

    last_error: AppError | None = None
    for attempt in attempts:
        model = attempt.get("model")
        if not model:
            continue
        try:
            return ai_service.synthesize_speech(
                db,
                prepared,
                feature=_FEATURE,
                model=model,
                voice=str(attempt["voice"]),
                speed=attempt.get("speed"),
                instructions=attempt.get("instructions"),
            )
        except AppError as exc:
            if exc.code in ("AI_UNSUPPORTED", "AI_DISABLED"):
                raise
            last_error = exc
            logger.info("Interviewer TTS fallback after %s on model %s", exc.code, model)

    if last_error:
        raise last_error
    return b""
