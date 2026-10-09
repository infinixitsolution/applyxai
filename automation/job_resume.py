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
    ext = ".docx"
    dispo = resp.headers.get("Content-Disposition") or ""
    m = re.search(r'filename="?([^";]+)"?', dispo)
    if m and "." in m.group(1):
        ext = Path(m.group(1)).suffix or ext
    out_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(job_id)}-tailored{ext}"
    out_path.write_bytes(resp.content)
    return str(out_path.resolve()), resume_id
