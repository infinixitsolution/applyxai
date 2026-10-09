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
_EMBED_TIMEOUT = 60.0


class AiTask(str, Enum):
    APP_ANSWER = "app_answer"
    APP_ANSWER_SELECT = "app_answer_select"
    RESUME_MATCH = "resume_match"
    RESUME_TAILOR = "resume_tailor"
    RESUME_SCORE = "resume_score"
    RESUME_INTAKE = "resume_intake"
    JD_EXTRACT = "jd_extract"
    TEST = "test"


def _model_for_task(cfg: "EffectiveAi", task: AiTask) -> str:
    fast = {
        AiTask.APP_ANSWER,
        AiTask.APP_ANSWER_SELECT,
        AiTask.RESUME_MATCH,
        AiTask.RESUME_SCORE,
        AiTask.RESUME_INTAKE,
        AiTask.JD_EXTRACT,
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
    if cfg.provider == "gemini":
        return _gemini_complete(cfg, model, system, user, temperature, max_tokens)
    return _openai_chat(cfg, model, system, user, temperature, max_tokens)


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


def _openai_chat(cfg: EffectiveAi, model: str, system: str, user: str, temperature: float | None, max_tokens: int) -> str:
    url = f"{cfg.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    with httpx.Client(timeout=_CHAT_TIMEOUT) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        logger.warning("Chat API error %s: %s", resp.status_code, resp.text[:500])
        raise AppError("AI_ERROR", f"The AI provider returned an error ({resp.status_code}).", 502)
    data = resp.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError("AI_ERROR", "Unexpected response from the AI provider.", 502) from exc


def _gemini_complete(cfg: EffectiveAi, model: str, system: str, user: str, temperature: float | None, max_tokens: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": cfg.api_key}
    gen: dict[str, Any] = {"maxOutputTokens": max_tokens}
    if temperature is not None:
        gen["temperature"] = temperature
    body = {
        "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
        "generationConfig": gen,
    }
    with httpx.Client(timeout=_CHAT_TIMEOUT) as client:
        resp = client.post(url, params=params, json=body)
    if resp.status_code >= 400:
        logger.warning("Gemini API error %s: %s", resp.status_code, resp.text[:500])
        raise AppError("AI_ERROR", f"Gemini returned an error ({resp.status_code}).", 502)
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError("AI_ERROR", "Unexpected response from Gemini.", 502) from exc
