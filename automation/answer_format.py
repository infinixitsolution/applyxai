"""Infer whether a screening question expects a number vs free text, and normalize AI output."""

from __future__ import annotations

import re
from typing import Literal

AnswerFormat = Literal["choice", "number", "text"]

_NUMERIC_LABEL = re.compile(
    r"(?:"
    r"how many|number of|# of|years?\s+of|years?\s+experience|"
    r"months?\s+of|weeks?\s+of|notice\s+period|notice\s+period\s*\(|"
    r"salary|compensation|\bctc\b|pay\s+rate|hourly|annual|"
    r"gpa|grade point|percent|percentage|\b\d+\s*[-–]\s*\d+\s*scale|scale\s+of\s*1|"
    r"rate\s+per|expected\s+amount|current\s+amount|"
    r"people\s+did\s+you\s+manage|team\s+size|"
    r"proficiency\s*\(\s*1|confidence\s*\(\s*1"
    r")",
    re.IGNORECASE,
)


def infer_answer_format(label: str, question_type: str = "text") -> AnswerFormat:
    qt = (question_type or "text").strip().lower()
    if qt in ("select", "radio"):
        return "choice"
    if qt in ("number", "tel"):
        return "number"
    text = (label or "").strip()
    if _NUMERIC_LABEL.search(text):
        return "number"
    if re.search(r"\b\d+\s*\+?\s*years?\b", text, re.I):
        return "number"
    return "text"


def normalize_numeric_answer(label: str, answer: str) -> str:
    """Strip prose from AI answers so LinkedIn numeric fields accept the value."""
    raw = (answer or "").strip()
    if not raw:
        return raw
    compact = raw.replace(",", "")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", compact):
        return compact
    low = (label or "").lower()
    allow_decimal = any(k in low for k in ("salary", "ctc", "compensation", "pay", "lakh", "rate", "gpa"))
    pattern = r"-?\d[\d,]*(?:\.\d+)?" if allow_decimal else r"-?\d[\d,]*"
    match = re.search(pattern, raw)
    if match:
        return match.group(0).replace(",", "")
    digits = re.sub(r"\D", "", raw)
    return digits if digits else raw


def numeric_presets_for_label(label: str) -> list[str]:
    low = (label or "").lower()
    if "scale" in low and "1" in low:
        return [str(n) for n in range(1, 11)]
    if "notice" in low:
        return ["0", "7", "15", "30", "45", "60", "90"]
    if any(k in low for k in ("year", "experience", "how many")):
        return [str(n) for n in range(0, 21)]
    if any(k in low for k in ("salary", "ctc", "compensation", "pay")):
        return ["500000", "800000", "1000000", "1200000", "1500000", "2000000"]
    if "month" in low:
        return [str(n) for n in range(0, 25)]
    if "week" in low:
        return [str(n) for n in range(0, 53)]
    return [str(n) for n in range(0, 11)]


def text_presets_for_label(label: str) -> list[str]:
    low = (label or "").lower()
    if "authorized" in low or "legally" in low and "work" in low:
        return ["Yes", "No"]
    if "sponsor" in low or "visa" in low:
        return ["Yes", "No", "Not applicable"]
    if low.startswith("are you") or low.startswith("do you"):
        return ["Yes", "No"]
    return []
