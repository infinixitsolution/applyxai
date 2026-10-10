"""Prompt templates for mock interview turns and feedback."""

from __future__ import annotations

from backend.app.services.mock_interview_rubric import rubric_catalog_for_prompt

INTERVIEWER_JSON_RULES = (
    'Respond with ONLY valid JSON (no markdown): {"message": "<your spoken line>", "should_end": false}. '
    "Set should_end to true only when you are politely closing the interview after enough questions."
)

MAX_TURNS_BEFORE_END = 12
SUGGEST_END_AFTER_TURNS = 10
MOCK_INTERVIEW_MAX_DURATION_MINUTES = 30
MOCK_INTERVIEW_MAX_DURATION_SEC = MOCK_INTERVIEW_MAX_DURATION_MINUTES * 60


def normalize_interview_types(types: list[str]) -> list[str]:
    cleaned = [t for t in types if t]
    if "mixed" in cleaned:
        return ["mixed"]
    return cleaned or ["mixed"]


def types_label(types: list[str]) -> str:
    if types == ["mixed"]:
        return "mixed (rotate behavioral, technical, and HR-style questions)"
    labels = {
        "behavioral": "behavioral (STAR, past experience)",
        "technical": "technical (role-specific skills and problem-solving)",
        "hr": "HR / culture and motivation",
    }
    return ", ".join(labels.get(t, t) for t in types)


def interviewer_system_prompt(
    *, types: list[str], context: str, turn_count: int, minutes_remaining: int | None = None
) -> str:
    end_hint = ""
    if turn_count >= SUGGEST_END_AFTER_TURNS:
        end_hint = (
            f"\nYou have asked about {turn_count} questions. Wrap up within the next 1-2 turns unless the candidate "
            "still has major gaps to explore."
        )
    time_hint = (
        f"\nThis is a timed mock interview: maximum {MOCK_INTERVIEW_MAX_DURATION_MINUTES} minutes from the start. "
        "Pace yourself (roughly 2-4 minutes per exchange including the candidate's answer)."
    )
    if minutes_remaining is not None:
        if minutes_remaining <= 2:
            time_hint += (
                f"\nOnly about {minutes_remaining} minute(s) remain — thank the candidate and close the interview "
                "with should_end true; do not ask another question."
            )
        elif minutes_remaining <= 8:
            time_hint += f"\nAbout {minutes_remaining} minutes remain — ask at most one more question, then wrap up."
    return (
        "You are a professional hiring manager conducting a live mock job interview for the candidate below. "
        f"Interview focus: {types_label(types)}.\n"
        "Rules:\n"
        "- Every question MUST stay on the job description (JD) and the candidate's resume — companies, projects, "
        "and technologies they actually list. Follow the MOCK INTERVIEW QUESTION PLAN in the context.\n"
        "- Prefer STAR behavioral questions tied to a named employer or project from the resume that maps to a JD requirement.\n"
        "- Do not ask generic riddles, brain teasers, or topics that are neither in the JD nor supported by the resume.\n"
        "- Speak naturally in short paragraphs (2-4 sentences): brief acknowledgment, optional follow-up, then ONE clear question.\n"
        "- Do not invent facts about the candidate; use only the provided context.\n"
        "- Do not ask multiple unrelated questions in one turn.\n"
        "- Stay professional, encouraging, and conversational.\n"
        f"- Hard limit: end the interview after at most {MAX_TURNS_BEFORE_END} candidate answers.\n"
        f"{INTERVIEWER_JSON_RULES}\n"
        f"{time_hint}"
        f"{end_hint}\n\n"
        f"Candidate and role context:\n{context}"
    )


def opening_user_prompt() -> str:
    return (
        "Start the mock interview. Greet the candidate by first name if known, mention the role and company briefly, "
        "set expectations (this is practice). Your first question must come from the QUESTION PLAN: pick a JD requirement "
        "that overlaps the resume (skill, employer, or project) and ask them to walk through a specific example. "
        f"{INTERVIEWER_JSON_RULES}"
    )


def turn_user_prompt(candidate_answer: str, *, prior_interviewer_lines: list[str] | None = None) -> str:
    recap = ""
    if prior_interviewer_lines:
        joined = "\n---\n".join(prior_interviewer_lines[-8:])
        recap = (
            "You already asked (do not repeat the same topic; go deeper on JD+resume gaps not yet covered):\n"
            f"{joined}\n\n"
        )
    return (
        f"The candidate just answered:\n{candidate_answer}\n\n"
        f"{recap}"
        "Respond as the interviewer: brief acknowledgment, then ONE next question from the QUESTION PLAN — "
        "JD requirement + resume employer/project/technology. No off-topic questions. "
        f"{INTERVIEWER_JSON_RULES}"
    )


def feedback_system_prompt(*, context: str, types: list[str]) -> str:
    return (
        "You evaluate mock job interviews for hiring practice. Use ONLY the transcript (Candidate vs Interviewer lines) "
        "and the role context below. Do not invent answers the candidate did not give.\n"
        "Scoring rules:\n"
        "- Every dimension note must reference something the candidate actually said or explicitly note that they did not answer.\n"
        "- Do NOT use placeholder scores (never assign 20-40 when there is no evidence). Use 0-10 when a dimension was not demonstrated.\n"
        "- Technical depth: score 0-8 unless the candidate explained skills, tools, projects, or problem-solving in their own words.\n"
        "- Behavioral / STAR: score 0-10 unless they gave a specific past example with context and outcome.\n"
        "- If candidate_turns is 0 or answers are empty/filler, set overall_score to 0 and all dimension scores to 0.\n"
        "- If the transcript is thin, say so in knowledge_summary and score conservatively (typically overall below 15).\n"
        "- strengths/improvements: specific, actionable, tied to transcript moments.\n"
        "- question_breakdown: one entry per interviewer question in order (skip small talk); rate each candidate answer.\n"
        "- sample_answers: 2-4 real questions from the transcript with concrete stronger answer outlines.\n"
        "- rubric_scores: REQUIRED array with exactly 100 objects, one per parameter id 1-100 (see rubric below).\n"
        "  Use score null (not 0) when the transcript provides no evidence for that parameter.\n"
        "  Use 0-10 when the candidate had opportunity but showed no capability; use higher values only with explicit evidence.\n"
        "  Keep notes under 100 characters; omit notes when score is null.\n"
        "- For parameters 41-50 (coding execution): use null for non-coding roles unless coding was discussed; "
        "otherwise assess role-specific practical execution.\n"
        "Output ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "overall_score": 0-100 integer,\n'
        '  "knowledge_summary": "2-4 sentences on what the candidate proved they know vs clear gaps",\n'
        '  "rubric_scores": [{"id": 1, "score": null or 0-100, "notes": "optional string"}, ... ids 1 through 100],\n'
        '  "dimensions": [\n'
        '    {"key": "communication", "label": "Communication", "score": 0-100, "notes": "string"},\n'
        '    {"key": "technical", "label": "Technical depth", "score": 0-100, "notes": "string"},\n'
        '    {"key": "behavioral", "label": "Behavioral / STAR", "score": 0-100, "notes": "string"},\n'
        '    {"key": "role_fit", "label": "Role fit", "score": 0-100, "notes": "string"}\n'
        "  ],\n"
        '  "question_breakdown": [\n'
        '    {"question": "interviewer question text", "answer_quality": "strong|adequate|weak|missing", "notes": "string"}\n'
        "  ],\n"
        '  "strengths": ["string", ...],\n'
        '  "improvements": ["string", ...],\n'
        '  "sample_answers": [{"question": "string", "suggestion": "string"}, ...]\n'
        "}\n"
        f"Interview types practiced: {types_label(types)}.\n\n"
        f"{rubric_catalog_for_prompt()}\n\n"
        f"Context:\n{context}"
    )


def feedback_user_prompt(transcript: str, *, candidate_turns: int) -> str:
    extra = ""
    if candidate_turns == 0:
        extra = "There are ZERO candidate answers — set overall_score and every dimension score to 0.\n"
    return (
        f"Transcript ({candidate_turns} candidate answer(s)):\n{transcript}\n\n"
        f"{extra}"
        "Analyze each candidate answer against the role requirements. Mark answer_quality missing when no real answer exists. "
        "Produce the JSON feedback object."
    )
