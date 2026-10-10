"""Platform AI: admin-configured provider, models, and API key (never sent to clients)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.core.platform_defaults import DEFAULT_AI
from backend.app.services.platform_settings_service import EffectiveAi, get_effective_ai

logger = logging.getLogger("applyxai.ai")

_CHAT_TIMEOUT = 90.0


def _raise_for_provider_response(resp: httpx.Response, *, context: str = "API") -> None:
    """Map HTTP failures from OpenAI-compatible or Gemini calls to AppError."""
    if resp.status_code < 400:
        return
    logger.warning("AI %s error %s: %s", context, resp.status_code, resp.text[:500])
    if resp.status_code in (401, 403):
        raise AppError(
            "AI_AUTH_FAILED",
            "The platform AI API key was rejected. An admin should set a valid key under Admin → Settings → AI and run Test AI.",
            502,
        )
    if resp.status_code == 429:
        raise AppError("AI_RATE_LIMIT", "The AI provider rate limit was hit. Try again in a moment.", 502)
    raise AppError("AI_ERROR", f"The AI provider returned an error ({resp.status_code}).", 502)
_EMBED_TIMEOUT = 60.0
_AUDIO_TIMEOUT = 120.0


class AiTask(str, Enum):
    APP_ANSWER = "app_answer"
    APP_ANSWER_SELECT = "app_answer_select"
    RESUME_MATCH = "resume_match"
    RESUME_TAILOR = "resume_tailor"
    RESUME_SCORE = "resume_score"
    RESUME_INTAKE = "resume_intake"
    JD_EXTRACT = "jd_extract"
    MOCK_INTERVIEW = "mock_interview"
    MOCK_INTERVIEW_FEEDBACK = "mock_interview_feedback"
    TEST = "test"


def _model_for_task(cfg: "EffectiveAi", task: AiTask) -> str:
    fast = {
        AiTask.APP_ANSWER,
        AiTask.APP_ANSWER_SELECT,
        AiTask.RESUME_MATCH,
        AiTask.RESUME_SCORE,
        AiTask.RESUME_INTAKE,
        AiTask.JD_EXTRACT,
        AiTask.MOCK_INTERVIEW,
        AiTask.TEST,
    }
    return cfg.models["fast"] if task in fast else cfg.models["strong"]


def ai_available(db: Session | None, *, feature: str) -> bool:
    cfg = get_effective_ai(db)
    return cfg.feature_on(feature)


def complete(
    db: Session | None,
    task: AiTask,
    *,
    system: str,
    user: str,
    feature: str = "applications",
    temperature: float | None = 0.2,
    max_tokens: int = 1500,
) -> str:
    cfg = get_effective_ai(db)
    if not cfg.feature_on(feature):
        raise AppError("AI_DISABLED", "Platform AI is not enabled or configured for this feature.", 503)
    model = _model_for_task(cfg, task)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return complete_messages(db, task, messages=messages, feature=feature, temperature=temperature, max_tokens=max_tokens)


def _message_has_vision(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


def complete_messages(
    db: Session | None,
    task: AiTask,
    *,
    messages: list[dict[str, Any]],
    feature: str = "applications",
    temperature: float | None = 0.2,
    max_tokens: int = 1500,
) -> str:
    cfg = get_effective_ai(db)
    if not cfg.feature_on(feature):
        raise AppError("AI_DISABLED", "Platform AI is not enabled or configured for this feature.", 503)
    model = _model_for_task(cfg, task)
    if cfg.provider == "gemini":
        if _message_has_vision(messages):
            raise AppError(
                "AI_UNSUPPORTED",
                "Camera presentation analysis requires an OpenAI-compatible vision model.",
                503,
            )
        return _gemini_messages(cfg, model, messages, temperature, max_tokens)
    return _openai_messages(cfg, model, messages, temperature, max_tokens)


def transcribe_audio(db: Session | None, *, audio_bytes: bytes, filename: str, feature: str = "mock_interview") -> str:
    cfg = get_effective_ai(db)
    if not cfg.feature_on(feature):
        raise AppError("AI_DISABLED", "Platform AI is not enabled or configured for this feature.", 503)
    if cfg.provider == "gemini":
        raise AppError("AI_UNSUPPORTED", "Audio transcription requires an OpenAI-compatible provider.", 503)
    url = f"{cfg.base_url}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    files = {"file": (filename, audio_bytes)}
    data = {"model": "whisper-1"}
    with httpx.Client(timeout=_AUDIO_TIMEOUT) as client:
        resp = client.post(url, headers=headers, files=files, data=data)
    if resp.status_code >= 400:
        _raise_for_provider_response(resp, context="transcription")
    try:
        return (resp.json().get("text") or "").strip()
    except (TypeError, ValueError) as exc:
        raise AppError("AI_ERROR", "Unexpected transcription response.", 502) from exc


def synthesize_speech(
    db: Session | None,
    text: str,
    *,
    feature: str = "mock_interview",
    voice: str = "nova",
    model: str = "tts-1",
    instructions: str | None = None,
    speed: float | None = None,
) -> bytes:
    cfg = get_effective_ai(db)
    if not cfg.feature_on(feature):
        raise AppError("AI_DISABLED", "Platform AI is not enabled or configured for this feature.", 503)
    if cfg.provider == "gemini":
        raise AppError("AI_UNSUPPORTED", "Speech synthesis requires an OpenAI-compatible provider.", 503)
    snippet = (text or "").strip()[:4096]
    if not snippet:
        return b""
    url = f"{cfg.base_url}/audio/speech"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {"model": model, "input": snippet, "voice": voice, "response_format": "mp3"}
    if instructions:
        body["instructions"] = instructions.strip()[:4096]
    if speed is not None:
        body["speed"] = max(0.25, min(4.0, float(speed)))
    with httpx.Client(timeout=_AUDIO_TIMEOUT) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        _raise_for_provider_response(resp, context="speech")
    return resp.content


def embed(db: Session | None, texts: list[str], *, feature: str = "resume") -> list[list[float]]:
    cfg = get_effective_ai(db)
    if not cfg.feature_on(feature):
        raise AppError("AI_DISABLED", "Platform AI is not enabled or configured for this feature.", 503)
    model = cfg.models.get("embedding") or "text-embedding-3-small"
    url = f"{cfg.base_url}/embeddings"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    body = {"model": model, "input": texts}
    with httpx.Client(timeout=_EMBED_TIMEOUT) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        logger.warning("Embedding API error %s: %s", resp.status_code, resp.text[:500])
        raise AppError("AI_ERROR", "The AI provider rejected the embedding request.", 502)
    data = resp.json()
    items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
    return [item["embedding"] for item in items]


def _openai_messages(
    cfg: EffectiveAi, model: str, messages: list[dict[str, Any]], temperature: float | None, max_tokens: int
) -> str:
    url = f"{cfg.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    with httpx.Client(timeout=_CHAT_TIMEOUT) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        _raise_for_provider_response(resp, context="chat")
    data = resp.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError("AI_ERROR", "Unexpected response from the AI provider.", 502) from exc


def _openai_chat(cfg: EffectiveAi, model: str, system: str, user: str, temperature: float | None, max_tokens: int) -> str:
    return _openai_messages(
        cfg, model, [{"role": "system", "content": system}, {"role": "user", "content": user}], temperature, max_tokens
    )


def _gemini_messages(
    cfg: EffectiveAi, model: str, messages: list[dict[str, str]], temperature: float | None, max_tokens: int
) -> str:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    contents: list[dict] = []
    for msg in messages:
        if msg.get("role") == "user":
            contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        elif msg.get("role") == "assistant":
            contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "Begin."}]}]
    return _gemini_complete(cfg, model, system, "", temperature, max_tokens, contents=contents)


def _gemini_complete(
    cfg: EffectiveAi,
    model: str,
    system: str,
    user: str,
    temperature: float | None,
    max_tokens: int,
    *,
    contents: list[dict] | None = None,
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": cfg.api_key}
    gen: dict[str, Any] = {"maxOutputTokens": max_tokens}
    if temperature is not None:
        gen["temperature"] = temperature
    if contents is None:
        contents = [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}]
    body: dict[str, Any] = {"contents": contents, "generationConfig": gen}
    if system.strip():
        body["systemInstruction"] = {"parts": [{"text": system}]}
    with httpx.Client(timeout=_CHAT_TIMEOUT) as client:
        resp = client.post(url, params=params, json=body)
    if resp.status_code >= 400:
        _raise_for_provider_response(resp, context="Gemini")
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError("AI_ERROR", "Unexpected response from Gemini.", 502) from exc
