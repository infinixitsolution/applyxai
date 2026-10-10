"""Resolve application answers: custom human patterns, then platform AI proxy."""

from __future__ import annotations

import logging
import os
from typing import Callable

import requests

log = logging.getLogger(__name__)

_API_BASE = ""
_AGENT_TOKEN = ""
_RUN_ID = ""
_LOCAL_ANSWER: Callable[..., str] | None = None


def configure(*, api_base: str = "", token: str = "", run_id: str = "",
              local_answer: Callable[..., str] | None = None) -> None:
    global _API_BASE, _AGENT_TOKEN, _RUN_ID, _LOCAL_ANSWER
    _API_BASE = (api_base or os.environ.get("APPLYXAI_API_BASE") or "").rstrip("/")
    _AGENT_TOKEN = token or os.environ.get("APPLYXAI_AGENT_TOKEN") or ""
    _RUN_ID = run_id or os.environ.get("APPLYXAI_RUN_ID") or ""
    _LOCAL_ANSWER = local_answer


def match_human_custom(label: str, human_questions: list) -> str | None:
    text = (label or "").strip()
    lower = text.lower()
    for item in human_questions or []:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern") or "").strip()
        if not pattern:
            continue
        match = (item.get("match") or "contains").lower()
        if match == "exact" and lower == pattern.lower():
            return str(item.get("answer") or "")
        if match != "exact" and pattern.lower() in lower:
            return str(item.get("answer") or "")
    return None


def _deny_list(ai_policy: dict) -> list[str]:
    raw = (ai_policy or {}).get("deny_label_contains") or []
    return [str(x).lower() for x in raw if str(x).strip()]


def can_use_ai(label_lower: str, question_type: str, ai_policy: dict) -> bool:
    if question_type not in ("text", "textarea", "select", "radio"):
        return False
    for d in _deny_list(ai_policy):
        if d in label_lower:
            return False
    return True


_PLACEHOLDER_COVERS = {
    "cover letter",
    "coverletter",
    "your cover letter",
    "n/a",
    "na",
    "none",
    "user information",
}


def is_placeholder_cover(text: str) -> bool:
    """True when the saved cover letter is empty or the stock placeholder, not a real letter."""
    compact = " ".join((text or "").split()).strip()
    if not compact:
        return True
    low = compact.lower().strip(" .")
    if low in _PLACEHOLDER_COVERS:
        return True
    return len(compact) < 40


def ask_cover_letter(
    *,
    job_description: str | None = None,
    job_title: str = "",
    company: str = "",
) -> str:
    """JD-specific cover letter from platform AI. Empty string when the API is unavailable."""
    if not (_API_BASE and _AGENT_TOKEN and _RUN_ID):
        return ""
    headers = {"Authorization": f"Bearer {_AGENT_TOKEN}", "Content-Type": "application/json"}
    body = {
        "job_description": (job_description or "")[:12000],
        "job_title": (job_title or "")[:300],
        "company": (company or "")[:300],
    }
    try:
        resp = requests.post(
            f"{_API_BASE}/api/agent/runs/{_RUN_ID}/ai/cover-letter",
            json=body,
            headers=headers,
            timeout=90,
        )
        data = resp.json()
        if resp.status_code == 200 and isinstance(data, dict) and data.get("success"):
            letter = (data.get("data") or {}).get("cover_letter") or ""
            return str(letter).strip()
        log.warning("Cover letter API returned %s: %s", resp.status_code, (resp.text or "")[:240])
    except (requests.RequestException, ValueError, TypeError) as exc:
        log.warning("Cover letter request failed: %s", exc)
    return ""


def ask_platform_ai(
    *,
    label: str,
    question_type: str,
    options: list[str] | None = None,
    job_description: str | None = None,
    job_title: str = "",
    company: str = "",
    user_information_all: str = "",
) -> str:
    if _API_BASE and _AGENT_TOKEN and _RUN_ID:
        headers = {"Authorization": f"Bearer {_AGENT_TOKEN}", "Content-Type": "application/json"}
        body = {
            "question": label,
            "question_type": question_type,
            "options": list(options or [])[:80],
            "job_description": (job_description or "")[:12000],
            "job_title": job_title[:300],
            "company": company[:300],
        }
        try:
            resp = requests.post(
                f"{_API_BASE}/api/agent/runs/{_RUN_ID}/ai/answer",
                json=body,
                headers=headers,
                timeout=90,
            )
            data = resp.json()
            if resp.status_code == 200 and isinstance(data, dict) and data.get("success"):
                ans = (data.get("data") or {}).get("answer") or ""
                return str(ans).strip()
            log.warning("AI answer API returned %s: %s", resp.status_code, (resp.text or "")[:240])
        except (requests.RequestException, ValueError, TypeError) as exc:
            log.warning("AI answer request failed: %s", exc)
    if _LOCAL_ANSWER is not None:
        try:
            return (_LOCAL_ANSWER(label, question_type=question_type, job_description=job_description,
                                  user_information_all=user_information_all) or "").strip()
        except Exception:
            pass
    return ""


def resolve_missing_answer(
    *,
    label_org: str,
    label_lower: str,
    question_type: str,
    human_questions: list,
    ai_policy: dict,
    use_ai: bool,
    options: list[str] | None = None,
    job_description: str | None = None,
    job_title: str = "",
    company: str = "",
    user_information_all: str = "",
    platform_proxy: bool = False,
) -> str | None:
    custom = match_human_custom(label_org, human_questions)
    if custom is not None and str(custom).strip():
        return str(custom).strip()
    try_ai = bool(use_ai) or bool(platform_proxy and _API_BASE and _AGENT_TOKEN and _RUN_ID)
    if try_ai and can_use_ai(label_lower, question_type, ai_policy):
        ai = ask_platform_ai(
            label=label_org,
            question_type=question_type,
            options=options,
            job_description=job_description,
            job_title=job_title,
            company=company,
            user_information_all=user_information_all,
        )
        if ai:
            return ai
    return None
