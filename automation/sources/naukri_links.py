"""Naukri URLs and apply-button classification. No browser dependency."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

_JOB_ID_RE = re.compile(r"(\d{6,})")


_DATE_JOB_AGE = {
    "past 24 hours": "1",
    "past week": "7",
    "past month": "30",
}


def job_age_days(date_posted: str) -> str:
    """Naukri jobAge query value for a LinkedIn-style date_posted label."""
    return _DATE_JOB_AGE.get((date_posted or "").strip().lower(), "")


def experience_filter(years: str | int | None) -> int | None:
    """Naukri experience= years, or None when the profile does not set a cap."""
    if years in (None, "", -1, "-1"):
        return None
    try:
        value = int(float(str(years).strip()))
    except (TypeError, ValueError):
        return None
    return max(value, 0)


def search_url(
    keyword: str,
    location: str,
    *,
    date_posted: str = "",
    experience_years: str | int | None = None,
) -> str:
    query = quote_plus((keyword or "").strip())
    parts = [f"k={query}"]
    place = quote_plus((location or "").strip())
    if place:
        parts.append(f"l={place}")
    age = job_age_days(date_posted)
    if age:
        parts.append(f"jobAge={age}")
    years = experience_filter(experience_years)
    if years is not None:
        parts.append(f"experience={years}")
    return "https://www.naukri.com/jobs?" + "&".join(parts)


def is_submit_control(label: str) -> bool:
    """True for a real submit/send control. Never the job-page Apply button."""
    low = " ".join((label or "").split()).lower()
    if not low or "apply" in low:
        return False
    return low in {"submit", "send", "save and continue"} or low.startswith("submit")


def listing_skip_reason(
    title: str,
    company: str,
    description: str,
    *,
    bad_words: list[str] | None = None,
    company_bad_words: list[str] | None = None,
) -> str:
    """Why this Naukri card should be skipped, or '' to apply."""
    company_text = company or ""
    blob = f"{title} {company} {description}"
    for word in company_bad_words or []:
        token = str(word).strip()
        if token and token.lower() in company_text.lower():
            return f'Company matches skip list "{token}"'
    for word in bad_words or []:
        token = str(word).strip()
        if not token:
            continue
        if re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", blob, re.I):
            return f'Contains skipped phrase "{token}"'
    return ""


def job_id_from_url(url: str) -> str:
    match = _JOB_ID_RE.search(url or "")
    return match.group(1) if match else ""


def job_page_url(job_id: str) -> str:
    return f"https://www.naukri.com/job-listings-{job_id}"


def fresher_or_experienced(years: str | int | None) -> str:
    """Naukri's first apply question. Zero years is Fresher; any recorded experience is Experienced."""
    try:
        total = int(float(str(years if years is not None else "").strip() or "0"))
    except ValueError:
        total = 0
    return "Fresher" if total <= 0 else "Experienced"


def actionable_question(question: str) -> str:
    """Drop Naukri's 'couldn't understand' preface and keep the question it is repeating."""
    text = " ".join((question or "").split())
    lower = text.lower()
    for phrase in ("couldn't understand", "couldn’t understand", "could not understand"):
        at = lower.find(phrase)
        if at == -1:
            continue
        rest = text[at + len(phrase):].lstrip(" .!:")
        if rest:
            return rest
    return text


def chat_step(question: str) -> str:
    """How this Naukri chat turn must be answered: resume, choice, or text.

    A choice is clicked. It is never typed into the message box.
    """
    asked = actionable_question(question).lower()
    if any(phrase in asked for phrase in ("upload your resume", "upload resume", "attach resume", "attach your resume", "upload cv", "update your resume")):
        return "resume"
    if "fresher" in asked and "experience" in asked:
        return "choice"
    choice_phrases = (
        "highest education", "education level", "which course", "course did you",
        "specialization", "specialisation", "course type",
        "qualification", "select your degree", "select your course",
        "select your education", "highest qualification",
    )
    if any(phrase in asked for phrase in choice_phrases):
        return "choice"
    return "text"


def _education_rows(education: list | None) -> list[dict]:
    rows: list[dict] = []
    for item in education or []:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _primary_education(education: list | None) -> dict:
    rows = _education_rows(education)
    if not rows:
        return {}
    return max(rows, key=lambda row: str(row.get("end_year") or row.get("start_year") or ""))


def _degree_tokens(degree: str, field: str) -> list[str]:
    combined = f"{degree} {field}".lower()
    tokens: list[str] = []
    if any(x in combined for x in ("ph.d", "phd", "doctorate", "doctoral")):
        tokens.extend(["Doctorate", "Ph.D", "PhD"])
    if any(x in combined for x in ("master", "mba", "m.tech", "mtech", "msc", "m.sc", "m.e.", "mca", "pgdm", "post grad")):
        tokens.extend(["Post Graduation", "Post Graduate", "MBA", "M.Tech", "M.E.", "M.Sc"])
    if any(x in combined for x in ("bachelor", "b.tech", "btech", "b.e.", "b.e ", "bsc", "b.sc", "bca", "bba", "b.com", "bcom", "undergrad")):
        tokens.extend(["B.Tech / B.E.", "B.E.", "B.Tech", "Graduation", "Graduate"])
    if re.search(r"\bbe\b", combined) and "mba" not in combined:
        tokens.extend(["B.Tech / B.E.", "B.E.", "Graduation"])
    if any(x in combined for x in ("diploma", "polytechnic")):
        tokens.append("Diploma")
    if "12th" in combined or "hsc" in combined or "higher secondary" in combined:
        tokens.append("12th Pass")
    if "10th" in combined or "ssc" in combined or "matriculation" in combined:
        tokens.append("10th Pass")
    return tokens


def education_level_answer(education: list | None) -> str | None:
    """Naukri's qualification chips: Graduation, Post Graduation, Diploma, Doctorate."""
    row = _primary_education(education)
    if not row:
        return None
    degree = str(row.get("degree") or "")
    field = str(row.get("field") or "")
    tokens = _degree_tokens(degree, field)
    if any(t in ("Doctorate", "Ph.D", "PhD") for t in tokens):
        return "Doctorate"
    if any(t in ("Post Graduation", "Post Graduate", "MBA", "M.Tech", "M.E.", "M.Sc") for t in tokens):
        return "Post Graduation"
    if "Diploma" in tokens and not any(t in ("Graduation", "Graduate", "B.Tech / B.E.", "B.E.", "B.Tech") for t in tokens):
        return "Diploma"
    if "12th Pass" in tokens:
        return "12th Pass"
    if "10th Pass" in tokens:
        return "10th Pass"
    if tokens or degree.strip():
        return "Graduation"
    return None


def education_course_answer(education: list | None) -> str | None:
    row = _primary_education(education)
    if not row:
        return None
    degree = str(row.get("degree") or "").strip()
    field = str(row.get("field") or "").strip()
    tokens = _degree_tokens(degree, field)
    for preferred in ("B.Tech / B.E.", "MBA", "M.Tech", "M.E.", "M.Sc", "B.E.", "B.Tech"):
        if preferred in tokens:
            return preferred
    if degree:
        return degree[:80]
    return field[:80] if field else None


def education_specialization_answer(education: list | None) -> str | None:
    row = _primary_education(education)
    if not row:
        return None
    field = str(row.get("field") or "").strip()
    if field:
        return field[:80]
    degree = str(row.get("degree") or "").strip()
    return degree[:80] if degree else None


def education_institute_answer(education: list | None) -> str | None:
    row = _primary_education(education)
    school = str(row.get("school") or "").strip()
    return school[:120] if school else None


def education_year_answer(education: list | None) -> str | None:
    row = _primary_education(education)
    raw = str(row.get("end_year") or row.get("year") or "")
    match = re.search(r"(19|20)\d{2}", raw)
    return match.group(0) if match else None


def _is_education_level_question(asked: str) -> bool:
    return any(
        phrase in asked
        for phrase in (
            "highest education", "education level", "highest qualification",
            "select your qualification", "your qualification", "qualification",
            "select your education",
        )
    )


def _is_course_question(asked: str) -> bool:
    return any(
        phrase in asked
        for phrase in ("which course", "course did you", "course type", "select your course", "select your degree", "your degree")
    )


def preferred_chat_answer(
    question: str,
    years: str | int | None = None,
    *,
    education: list | None = None,
) -> str | None:
    """A configured answer for a Naukri chat question, when the profile already decides it."""
    asked = actionable_question(question).lower()
    if "fresher" in asked and "experience" in asked:
        return fresher_or_experienced(years)
    if ("resume" in asked or "cv" in asked) and any(word in asked for word in ("use", "this", "existing", "current")):
        return "Yes"
    if _is_education_level_question(asked):
        return education_level_answer(education)
    if _is_course_question(asked):
        return education_course_answer(education)
    if "specialization" in asked or "specialisation" in asked:
        return education_specialization_answer(education)
    if "institute" in asked or "college" in asked or "university" in asked:
        return education_institute_answer(education)
    if any(phrase in asked for phrase in ("passing year", "year of passing", "graduation year", "end year")):
        return education_year_answer(education)
    return None


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


_OPTION_ALIASES = (
    ("graduateordiploma", ("graduation", "graduate", "ug", "undergrad", "bachelors", "bachelor")),
    ("graduation", ("graduateordiploma", "graduate", "bachelors", "bachelor", "ug")),
    ("postgraduate", ("postgraduation", "pg", "masters", "master", "mba", "mtech")),
    ("postgraduation", ("postgraduate", "pg", "masters", "master")),
    ("doctorate", ("phd", "phd", "doctoral")),
    ("btechbe", ("btech", "be", "btechbe")),
    ("btech", ("btechbe", "be")),
    ("computerscience", ("computerscienceengineering", "cse", "cs", "computereng", "computerengineering")),
    ("12thpass", ("12th", "hsc", "highersecondary", "intermediate")),
    ("10thpass", ("10th", "ssc", "matriculation")),
)


def pick_option(answer: str | None, options: list[str]) -> str | None:
    """The visible choice that matches answer, or None when none of them honestly does."""
    want = " ".join((answer or "").split()).lower()
    choices = [" ".join(option.split()) for option in options if " ".join(option.split())]
    if not want or not choices:
        return None
    compact_want = _compact(want)
    scored: list[tuple[int, int, str]] = []
    alias_targets = {compact_want}
    for key, aliases in _OPTION_ALIASES:
        compact_aliases = {_compact(a) for a in aliases} | {key}
        if compact_want in compact_aliases:
            alias_targets |= compact_aliases
    for index, choice in enumerate(choices):
        compact_choice = _compact(choice)
        lower = choice.lower()
        score = 0
        if lower == want or compact_choice == compact_want:
            score = 100
        elif compact_choice in alias_targets:
            score = 80
        elif lower in want:
            score = 60
        elif len(want) >= 4 and (want in lower or compact_want in compact_choice):
            score = 50
        elif len(compact_choice) >= 4 and compact_choice in compact_want:
            score = 40
        if score:
            scored.append((score, -index, choice))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][2]


def pick_education_option(options: list[str], education: list | None) -> str | None:
    """When Naukri shows qualification chips, pick the one that matches the profile."""
    candidates = [
        education_level_answer(education),
        education_course_answer(education),
        education_specialization_answer(education),
        education_institute_answer(education),
        education_year_answer(education),
    ]
    for candidate in candidates:
        hit = pick_option(candidate, options)
        if hit:
            return hit
    return None


def keep_leaf_chat_options(labels: list[str]) -> list[str]:
    """Drop a wrapper whose text concatenates several chips. Keep 'Post Graduation'."""
    kept: list[str] = []
    for label in labels:
        others = [other for other in labels if other.lower() != label.lower()]
        hits = sum(1 for other in others if other.lower() in label.lower())
        if hits >= 2:
            continue
        kept.append(label)
    return kept


def classify_apply(text: str, left_naukri: bool) -> str:
    """'external' when the control leaves Naukri or is a company-site apply. Otherwise 'onsite'."""
    label = " ".join((text or "").split()).lower()
    if left_naukri or "company site" in label or "company website" in label:
        return "external"
    return "onsite"
