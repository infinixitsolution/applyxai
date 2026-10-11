"""Per-job resume path: optional platform AI tailor before LinkedIn upload."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from datetime import datetime
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


def skills_for_filename(skills, job_title: str = "") -> str | list:
    """Normalize extracted JD skills (or job title) for the resume filename."""
    if isinstance(skills, dict):
        parts: list[str] = []
        for key in (
            "technical_skills",
            "technical",
            "required_skills",
            "skills",
            "soft_skills",
            "tools",
        ):
            raw = skills.get(key)
            if isinstance(raw, list):
                parts.extend(str(x) for x in raw if str(x).strip())
            elif raw:
                parts.append(str(raw))
        if parts:
            return parts[:4]
    if isinstance(skills, list):
        return [str(x) for x in skills[:4] if str(x).strip()]
    if isinstance(skills, str) and skills.strip() and "error" not in skills.lower():
        return skills
    return job_title or "General"


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


def _parse_linkedin_resume_date(full: str) -> datetime | None:
    text = (full or "").replace("\u2026", "")
    match = re.search(
        r"(?:uploaded on|last used on)\s+(\d{1,2}/\d{1,2}/\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%m/%d/%Y")
    except ValueError:
        return None


def resume_row_rank(filename: str, label: str, full: str = "") -> tuple:
    """Higher tuple sorts first: filename match, fresh upload, newest date, later index."""
    score = resume_label_score(filename, label)
    blob = (full or label or "").lower()
    uploaded = "uploaded on" in blob
    last_used = "last used on" in blob
    when = _parse_linkedin_resume_date(full or label)
    date_ord = when.toordinal() if when else 0
    return (score, 1 if uploaded else 0, 0 if last_used else 1, date_ord)


def job_resume_dir(cache_dir: str, job_id: str) -> Path:
    """Per-job folder under the run cache: ``{cache_dir}/jobs/{job_id}/``."""
    base = Path(cache_dir or ".")
    return base / "jobs" / (_safe_name(job_id) or "unknown")


def prepare_resume_for_job(
    source_path: str,
    *,
    job_id: str,
    job_title: str = "",
    company: str = "",
    cache_dir: str = "",
    candidate: str = "",
    skills: str | list | None = None,
    experience: str | int | None = None,
    version: int | None = None,
) -> str:
    """Copy the resume into a JD folder as ``{candidate}_{skills}_{experience}_v-N.ext``."""
    from automation.resume_naming import build_resume_filename, next_resume_version

    path = Path(source_path)
    if not path.is_file():
        return source_path
    skill_fallback = job_title or company or "General"
    cand = candidate or path.stem
    exp = experience if experience is not None else "0"
    ver = version if version is not None else next_resume_version(cache_dir=cache_dir)
    ext = path.suffix or ".pdf"
    dest_name = build_resume_filename(
        candidate=cand,
        skills=skills if skills is not None else skill_fallback,
        experience=exp,
        version=ver,
        ext=ext,
    )
    dest_dir = job_resume_dir(cache_dir, job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if path.parent.resolve() == dest_dir.resolve() and "_v-" in path.name.lower():
        return str(path.resolve())
    dest = dest_dir / dest_name
    if path.resolve() != dest.resolve():
        shutil.copy2(path, dest)
    return str(dest.resolve())


def stage_for_linkedin_upload(
    source_path: str,
    *,
    job_id: str = "",
    job_title: str = "",
    company: str = "",
    cache_dir: str = "",
    candidate: str = "",
    skills: str | list | None = None,
    experience: str | int | None = None,
    version: int | None = None,
) -> str:
    return prepare_resume_for_job(
        source_path,
        job_id=job_id,
        job_title=job_title,
        company=company,
        cache_dir=cache_dir,
        candidate=candidate,
        skills=skills,
        experience=experience,
        version=version,
    )


def choose_resume_after_upload(
    labels: list[str],
    filename: str,
    before: list[str] | None = None,
    *,
    full_texts: list[str] | None = None,
) -> int | None:
    """Pick the resume row to use after upload (handles duplicate LinkedIn display names)."""
    before = before or []
    fulls = full_texts if full_texts and len(full_texts) == len(labels) else labels
    choice = choose_resume_card(labels, filename, before, full_texts=fulls)
    if choice is not None:
        return choice
    if len(labels) > len(before):
        pool = list(range(len(before), len(labels)))
        return max(pool, key=lambda index: resume_row_rank(filename, labels[index], fulls[index]))
    if labels:
        return max(range(len(labels)), key=lambda index: resume_row_rank(filename, labels[index], fulls[index]))
    return None


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


def choose_resume_card(
    labels: list[str],
    filename: str,
    before: list[str] | None = None,
    *,
    full_texts: list[str] | None = None,
) -> int | None:
    """Index of the resume to use: the file just added, otherwise the best filename match."""
    if not labels:
        return None
    before = before or []
    before_norm = {normalize_resume_label(item) for item in before}
    fulls = full_texts if full_texts and len(full_texts) == len(labels) else labels

    def rank(index: int) -> tuple:
        return resume_row_rank(filename, labels[index], fulls[index])

    novel = [
        index for index, label in enumerate(labels)
        if normalize_resume_label(label) not in before_norm
    ]
    pool = list(range(len(labels)))
    if novel and len(labels) <= len(before):
        pool = novel
    strong = [index for index in pool if rank(index)[0] >= 600]
    if not strong and novel:
        strong = novel
    if not strong:
        return None
    return max(strong, key=lambda index: (rank(index), -index))


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
    candidate: str = "",
    skills: str | list | None = None,
    experience: str | int | None = None,
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
    out_dir = job_resume_dir(cache_dir, job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    dispo_name = local_resume_filename(dispo, job_id)
    ext = Path(dispo_name).suffix or ".docx"
    if "_v-" in dispo_name:
        out_name = dispo_name
    else:
        from automation.resume_naming import build_resume_filename, next_resume_version

        ver = next_resume_version(cache_dir=cache_dir, extra_names=[dispo_name])
        out_name = build_resume_filename(
            candidate=candidate or "Resume",
            skills=skills if skills is not None else (job_title or "General"),
            experience=experience if experience is not None else "0",
            version=ver,
            ext=ext,
        )
    out_path = out_dir / out_name
    out_path.write_bytes(resp.content)
    return str(out_path.resolve()), resume_id
