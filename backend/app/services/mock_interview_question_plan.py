"""Build JD ↔ resume alignment guidance for mock interview question selection."""

from __future__ import annotations

import re
from typing import Any

_STOP = frozenset(
    {
        "the", "and", "for", "with", "you", "your", "will", "our", "are", "this", "that", "from", "have", "has",
        "been", "able", "work", "team", "role", "job", "using", "use", "years", "year", "experience", "including",
        "other", "such", "into", "through", "about", "their", "they", "them", "what", "when", "where", "which",
        "must", "should", "would", "could", "can", "may", "also", "well", "all", "any", "per", "not", "but",
    }
)

_BULLET = re.compile(r"^[\s•·\-*]+|^\d+[.)]\s*")


def _tokenize_skills(text: str, *, limit: int = 60) -> list[str]:
    if not text:
        return []
    raw = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,48}", text)
    out: list[str] = []
    seen: set[str] = set()
    for tok in raw:
        low = tok.lower()
        if low in _STOP or len(low) < 2:
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def extract_jd_bullets(description: str) -> list[str]:
    bullets: list[str] = []
    for line in (description or "").splitlines():
        line = line.strip()
        if len(line) < 24:
            continue
        if _BULLET.match(line) or line.startswith(("Responsible", "Requirements", "Qualifications", "Must ", "Should ")):
            cleaned = _BULLET.sub("", line).strip()
            if len(cleaned) >= 20:
                bullets.append(cleaned[:400])
    if not bullets and description:
        for chunk in re.split(r"\.\s+", description[:4000]):
            chunk = chunk.strip()
            if 40 <= len(chunk) <= 400:
                bullets.append(chunk)
            if len(bullets) >= 15:
                break
    return bullets[:20]


def resume_profile_block(intake: dict[str, Any]) -> dict[str, Any]:
    work = [w for w in (intake.get("work_history") or []) if isinstance(w, dict)]
    companies: list[str] = []
    roles: list[str] = []
    project_lines: list[str] = []
    for w in work[:8]:
        co = str(w.get("company") or "").strip()
        title = str(w.get("title") or "").strip()
        if co and co not in companies:
            companies.append(co)
        if title:
            roles.append(f"{title}" + (f" @ {co}" if co else ""))
        summary = str(w.get("summary") or "").strip()
        if summary:
            project_lines.append(f"{co or 'Employer'} — {summary[:350]}")
    skills = [str(s).strip() for s in (intake.get("skills") or []) if str(s).strip()][:40]
    return {
        "companies": companies,
        "roles": roles,
        "skills": skills,
        "project_summaries": project_lines[:8],
        "summary": (intake.get("summary") or "")[:800],
        "current_title": intake.get("current_title"),
        "current_company": intake.get("current_company"),
    }


def jd_resume_overlap(jd_tokens: list[str], resume_skills: list[str]) -> tuple[list[str], list[str], list[str]]:
    jd_set = {t.lower() for t in jd_tokens}
    res_set = {t.lower() for t in resume_skills}
    overlap = sorted(jd_set & res_set, key=str.lower)[:25]
    jd_gaps = sorted(jd_set - res_set, key=str.lower)[:20]
    resume_strengths = sorted(res_set - jd_set, key=str.lower)[:20]
    return overlap, jd_gaps, resume_strengths


def build_question_plan(
    *,
    job_title: str,
    company: str,
    job_description: str,
    resume_intake: dict[str, Any] | None,
    profile_skills: list[str] | None = None,
) -> str:
    """Structured guidance appended to interviewer context."""
    jd_bullets = extract_jd_bullets(job_description)
    jd_tokens = _tokenize_skills(f"{job_title} {job_description}", limit=50)
    intake = resume_intake or {}
    profile = resume_profile_block(intake)
    skills = list(profile["skills"])
    for s in profile_skills or []:
        if s and s not in skills:
            skills.append(s)
    overlap, jd_gaps, resume_extra = jd_resume_overlap(jd_tokens, skills)

    lines = [
        "=== MOCK INTERVIEW QUESTION PLAN (follow strictly) ===",
        "Goal: every question must connect (1) a specific job requirement below with (2) the candidate's resume — "
        "employers, projects, tools, and outcomes they actually list. Do not drift into generic trivia or topics "
        "absent from the job description.",
        "",
        "Algorithm for each turn:",
        "- Pick one JD requirement or responsibility (prioritize overlap skills first, then recent employer projects, "
        "then JD gaps where resume shows adjacent experience).",
        "- Ask the candidate to explain with STAR (situation, task, action, result) using a named employer, project, "
        "or technology from their resume.",
        "- Do not invent companies, projects, or tools the candidate did not list.",
        "- Do not ask about frameworks/domains that appear neither in the JD nor on the resume.",
        "- Follow-ups must deepen the same JD+resume thread, not switch to unrelated interview clichés.",
        "",
        f"Target role: {job_title or 'Unknown title'}" + (f" at {company}" if company else ""),
        "",
        "Job description — key responsibilities (source for 'what to assess'):",
    ]
    if jd_bullets:
        lines.extend(f"- {b}" for b in jd_bullets)
    else:
        lines.append(f"- {(job_description or '')[:1200]}")
    lines.extend(
        [
            "",
            "Resume-derived candidate facts (only allowed source for their past work):",
        ]
    )
    if profile["roles"]:
        lines.append("Roles: " + "; ".join(profile["roles"][:6]))
    if profile["companies"]:
        lines.append("Companies: " + ", ".join(profile["companies"][:8]))
    if skills:
        lines.append("Skills / technologies on resume: " + ", ".join(skills[:30]))
    for ps in profile["project_summaries"][:5]:
        lines.append(f"Experience note: {ps}")
    if profile["summary"]:
        lines.append("Summary: " + str(profile["summary"])[:500])
    if not profile["roles"] and not skills and not profile["summary"]:
        lines.append("(Resume text was empty — ask only from JD and ask candidate to cite real examples from their background.)")
    lines.extend(
        [
            "",
            "JD ↔ resume alignment:",
            "Overlap (prefer these topics first): " + (", ".join(overlap) if overlap else "none detected — tie JD bullets to any concrete resume line"),
            "JD requirements with weak resume signal (probe honestly, allow adjacent experience): "
            + (", ".join(jd_gaps[:15]) if jd_gaps else "see JD bullets above"),
            "Extra resume strengths (use if JD-aligned): " + (", ".join(resume_extra[:12]) if resume_extra else "n/a"),
            "=== END QUESTION PLAN ===",
        ]
    )
    return "\n".join(lines)


def prior_interviewer_questions(messages: list[Any]) -> list[str]:
    """Extract interviewer lines already asked (avoid repeating topics)."""
    from backend.app.models.enums import MockInterviewMessageRole

    out: list[str] = []
    for msg in messages or []:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
        if role == MockInterviewMessageRole.INTERVIEWER or str(role).endswith("interviewer"):
            text = str(content).strip()
            if text:
                out.append(text[:500])
    return out
