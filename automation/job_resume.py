"""Per-job resume path: optional platform AI tailor before LinkedIn upload."""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_API_BASE = ""
_AGENT_TOKEN = ""
_RUN_ID = ""


def configure(*, api_base: str = "", token: str = "", run_id: str = "") -> None:
    global _API_BASE, _AGENT_TOKEN, _RUN_ID
    _API_BASE = (api_base or os.environ.get("APPLYXAI_API_BASE") or "").rstrip("/")
    _AGENT_TOKEN = token or os.environ.get("APPLYXAI_AGENT_TOKEN") or ""
    _RUN_ID = run_id or os.environ.get("APPLYXAI_RUN_ID") or ""


def _safe_name(job_id: str) -> str:
    return re.sub(r"[^\w.-]+", "_", job_id)[:64] or "job"


def local_resume_filename(content_disposition: str, job_id: str, default_ext: str = ".docx") -> str:
    """Save the tailored file under the JD version name LinkedIn will display."""
    match = re.search(r'filename="?([^";]+)"?', content_disposition or "")
    name = Path(match.group(1)).name if match else ""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name or name.lower() in {".docx", ".pdf", ".doc"}:
        name = f"{_safe_name(job_id)}-tailored{default_ext}"
    if not Path(name).suffix:
        name += default_ext
    return name[:180]


def normalize_resume_label(value: str) -> str:
    text = (value or "").replace("…", "").replace("...", "")
    text = os.path.splitext(text.strip())[0]
    return " ".join(text.lower().split())


def resume_label_score(filename: str, label: str) -> int:
    """How closely a LinkedIn card title matches the prepared file.

    A shared person name is not enough. Sibling resumes for other jobs must score 0
    so Easy Apply does not pick them.
    """
    stem = normalize_resume_label(os.path.basename(filename or ""))
    shown = normalize_resume_label(label)
    if not stem or not shown:
        return 0
    if stem == shown:
        return 1000
    if stem.startswith(shown) or shown.startswith(stem):
        return 600 + min(len(stem), len(shown))
    shared = 0
    for left, right in zip(stem, shown):
        if left != right:
            break
        shared += 1
    shorter = min(len(stem), len(shown))
    if shared >= 20 or (shared >= 12 and shared / shorter >= 0.7):
        return shared
    return 0


def choose_resume_card(labels: list[str], filename: str, before: list[str] | None = None) -> int | None:
    """Index of the resume to use: the file just added, otherwise an exact match of this file."""
    before_norm = {normalize_resume_label(item) for item in (before or [])}
    new_indexes = [
        index for index, label in enumerate(labels)
        if normalize_resume_label(label) not in before_norm
    ]
    if new_indexes:
        return max(
            new_indexes,
            key=lambda index: (resume_label_score(filename, labels[index]), -index),
        )
    best_index = None
    best_score = 0
    for index, label in enumerate(labels):
        score = resume_label_score(filename, label)
        if score >= 600 and score > best_score:
            best_score = score
            best_index = index
    return best_index


def wait_until_file_ready(path: str, *, timeout: float = 20, poll: float = 0.25) -> bool:
    """True once `path` exists, is non-empty, and its size stays the same across two checks."""
    deadline = time.time() + timeout
    last = -1
    while time.time() < deadline:
        if path and os.path.isfile(path):
            size = os.path.getsize(path)
            if size > 0 and size == last:
                return True
            last = size
        time.sleep(poll)
    return bool(path and os.path.isfile(path) and os.path.getsize(path) > 0)


def resolve_upload_path(
    *,
    resume_mode: str,
    default_path: str,
    job_id: str,
    job_description: str,
    job_title: str = "",
    company: str = "",
    cache_dir: str,
) -> tuple[str, str | None]:
    """
    Returns (absolute path for LinkedIn file input, resume UUID from platform if tailored).
    Falls back to default_path when tailoring is off or the API declines.
    """
    if resume_mode != "tailor_if_gate":
        return default_path, None
    jd = (job_description or "").strip()
    if not jd or jd == "Unknown":
        return default_path, None
    if not (_API_BASE and _AGENT_TOKEN and _RUN_ID and job_id):
        return default_path, None

    headers = {"Authorization": f"Bearer {_AGENT_TOKEN}", "Content-Type": "application/json"}
    body = {
        "job_description": jd[:12000],
        "job_title": (job_title or "")[:300],
        "company": (company or "")[:300],
    }
    url = f"{_API_BASE}/api/agent/runs/{_RUN_ID}/jobs/{job_id}/tailor"
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=180)
    except requests.RequestException as exc:
        log.warning("Tailor request failed for job %s: %s", job_id, exc)
        return default_path, None

    if resp.status_code == 422:
        log.info("Tailor skipped for job %s (gate or validation): %s", job_id, resp.text[:240])
        return default_path, None
    if resp.status_code >= 400:
        log.warning("Tailor API returned %s for job %s: %s", resp.status_code, job_id, resp.text[:240])
        return default_path, None

    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype.startswith("application/json"):
        log.warning("Tailor API returned JSON instead of a file for job %s", job_id)
        return default_path, None

    resume_id = (resp.headers.get("X-Resume-Id") or resp.headers.get("x-resume-id") or "").strip() or None
    dispo = resp.headers.get("Content-Disposition") or ""
    out_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / local_resume_filename(dispo, job_id)
    out_path.write_bytes(resp.content)
    return str(out_path.resolve()), resume_id
