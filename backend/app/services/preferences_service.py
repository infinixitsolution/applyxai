from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import uuid

from backend.app.models import ApplicationPreferences, SearchConfig, User, UserProfile
from backend.app.schemas.application_preferences import (
    DEFAULT_DENY,
    MAX_HUMAN_QUESTIONS,
    MAX_USER_INFO,
    HumanQuestionIn,
)
from backend.app.schemas.profile import ProfileIn, SearchConfigIn
from backend.app.services.ai_service import ai_available
from backend.app.services.engine_fields import APPLICATION_FIELDS, validate_mapping

_QA_KEYS = frozenset({"human_questions", "ai_applications_enabled", "user_information_all", "ai_policy"})
_MAX_PENDING_FORM_QUESTIONS = 120
_ALLOWED_Q_TYPES = frozenset({"text", "textarea", "select", "radio", "checkbox"})

_PROFILE_FIELDS = (
    "phone",
    "headline",
    "summary",
    "current_title",
    "current_company",
    "experience_years",
    "skills",
    "preferred_roles",
    "preferred_locations",
    "preferred_resume_template",
    "education",
    "work_history",
)


def get_profile(db: Session, user: User) -> dict:
    profile = user.profile
    data = {"email": user.email, "first_name": user.first_name, "last_name": user.last_name}
    for name in _PROFILE_FIELDS:
        data[name] = getattr(profile, name) if profile else None
    data["skills"] = data["skills"] or []
    data["preferred_roles"] = data["preferred_roles"] or []
    data["preferred_locations"] = data["preferred_locations"] or []
    data["preferred_resume_template"] = (
        getattr(profile, "preferred_resume_template", None) if profile else None
    ) or "modern"
    data["education"] = list(getattr(profile, "education", None) or []) if profile else []
    data["work_history"] = list(getattr(profile, "work_history", None) or []) if profile else []
    return data


def update_profile(db: Session, user: User, payload: ProfileIn) -> dict:
    user.first_name, user.last_name = payload.first_name, payload.last_name
    if user.profile is None:
        user.profile = UserProfile(user_id=user.id)
    for name in _PROFILE_FIELDS:
        value = getattr(payload, name)
        if name in ("education", "work_history"):
            setattr(user.profile, name, [e.model_dump() if hasattr(e, "model_dump") else e for e in (value or [])])
            continue
        if value is None and name != "experience_years":
            value = ""
        setattr(user.profile, name, value)
    db.commit()
    db.refresh(user)
    return get_profile(db, user)


def get_search(db: Session, user: User) -> SearchConfig | None:
    return db.scalar(select(SearchConfig).where(SearchConfig.user_id == user.id))


def update_search(db: Session, user: User, payload: SearchConfigIn) -> SearchConfig:
    config = get_search(db, user)
    if config is None:
        config = SearchConfig(user_id=user.id)
        db.add(config)
    for name, value in payload.model_dump().items():
        setattr(config, name, value)
    db.commit()
    db.refresh(config)
    return config


def _application_row(db: Session, user: User) -> ApplicationPreferences:
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    if prefs is None:
        prefs = ApplicationPreferences(user_id=user.id, answers={})
        db.add(prefs)
        db.flush()
    return prefs


def _validate_human_questions(raw: list) -> list[dict]:
    if len(raw) > MAX_HUMAN_QUESTIONS:
        raise ValueError(f"At most {MAX_HUMAN_QUESTIONS} custom questions are allowed")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each custom question must be an object")
        if not item.get("id"):
            item = {**item, "id": str(uuid.uuid4())}
        out.append(HumanQuestionIn.model_validate(item).model_dump())
    return out


def application_document(db: Session, user: User) -> dict:
    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    if prefs is None:
        return {
            "answers": {},
            "human_questions": [],
            "pending_form_questions": [],
            "ai_applications_enabled": False,
            "user_information_all": "",
            "ai_policy": {"deny_label_contains": list(DEFAULT_DENY)},
            "ai_available": ai_available(db, feature="applications"),
        }
    policy = prefs.ai_policy or {}
    return {
        "answers": dict(prefs.answers or {}),
        "human_questions": list(prefs.human_questions or []),
        "pending_form_questions": _public_pending(prefs.pending_form_questions or []),
        "ai_applications_enabled": bool(prefs.ai_applications_enabled),
        "user_information_all": prefs.user_information_all or "",
        "ai_policy": {"deny_label_contains": policy.get("deny_label_contains") or list(DEFAULT_DENY)},
        "ai_available": ai_available(db, feature="applications"),
    }


def _pending_key(label: str, question_type: str) -> str:
    return f"{question_type}:{(label or '').strip().lower()[:400]}"


def _public_pending(items: list) -> list:
    out = []
    for row in items:
        if not isinstance(row, dict):
            continue
        pub = {k: v for k, v in row.items() if k != "_key"}
        out.append(pub)
    return out


def _clean_label_for_pattern(label: str) -> str:
    text = (label or "").strip()
    if " [" in text:
        text = text.split(" [", 1)[0].strip()
    if text.endswith(" ]"):
        text = text[:-2].strip()
    return text[:500] or "Unknown question"


def capture_form_question(db: Session, user_id: uuid.UUID, event: dict, job_details: dict | None = None) -> None:
    """Append a LinkedIn form question seen during automation (deduped by label + type)."""
    user = db.get(User, user_id)
    if user is None:
        return
    prefs = _application_row(db, user)
    label = _clean_label_for_pattern(str(event.get("label") or ""))
    qtype = str(event.get("question_type") or "text").strip().lower()
    if qtype not in _ALLOWED_Q_TYPES:
        qtype = "text"
    options = event.get("options") if isinstance(event.get("options"), list) else []
    options = [str(o).strip()[:200] for o in options if str(o).strip()][:30]
    needs = bool(event.get("needs_answer"))
    details = job_details or {}
    key = _pending_key(label, qtype)
    pending = list(prefs.pending_form_questions or [])
    hit = next((p for p in pending if p.get("_key") == key), None)
    now = datetime.now(timezone.utc).isoformat()
    if hit:
        hit["times_seen"] = int(hit.get("times_seen") or 1) + 1
        hit["last_seen_at"] = now
        if needs:
            hit["needs_answer"] = True
        if options and not hit.get("options"):
            hit["options"] = options
    else:
        pending.append({
            "id": str(uuid.uuid4()),
            "_key": key,
            "label": label,
            "question_type": qtype,
            "options": options,
            "job_id": str(event.get("job_id") or details.get("job_id") or "")[:64],
            "job_title": str(details.get("title") or "")[:200],
            "company": str(details.get("company") or "")[:200],
            "needs_answer": needs,
            "times_seen": 1,
            "first_seen_at": now,
            "last_seen_at": now,
        })
    if len(pending) > _MAX_PENDING_FORM_QUESTIONS:
        pending = pending[-_MAX_PENDING_FORM_QUESTIONS:]
    prefs.pending_form_questions = pending
    db.flush()


def resolve_pending_questions(db: Session, user: User, answers: list[dict]) -> dict:
    """Save answers for pending questions as custom human_questions and remove them from pending."""
    prefs = _application_row(db, user)
    pending = list(prefs.pending_form_questions or [])
    human = list(prefs.human_questions or [])
    by_id = {p["id"]: p for p in pending if p.get("id")}
    for row in answers:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        answer = str(row.get("answer") or "").strip()
        if not pid or not answer:
            continue
        item = by_id.get(pid)
        if item is None:
            continue
        qtype = item.get("question_type") or "text"
        field_types = [qtype] if qtype in _ALLOWED_Q_TYPES else ["text", "textarea", "select", "radio"]
        pattern = _clean_label_for_pattern(item.get("label") or "")
        human.append(HumanQuestionIn(
            match="contains",
            pattern=pattern,
            answer=answer[:2000],
            field_types=field_types,
        ).model_dump())
        for p in pending:
            if p.get("id") == pid:
                p["needs_answer"] = False
                p["has_saved_rule"] = True
                break
    if len(human) > MAX_HUMAN_QUESTIONS:
        raise ValueError(f"At most {MAX_HUMAN_QUESTIONS} custom questions are allowed")
    prefs.human_questions = _validate_human_questions(human)
    prefs.pending_form_questions = pending
    db.commit()
    return application_document(db, user)


def get_application(db: Session, user: User) -> dict:
    return application_document(db, user)


def update_application(db: Session, user: User, changes: dict) -> dict:
    """Merge engine answer keys; null removes. QA keys replace when present."""
    answer_changes = {k: v for k, v in changes.items() if k not in _QA_KEYS}
    cleaned = validate_mapping(APPLICATION_FIELDS, answer_changes, allow_null=True) if answer_changes else {}
    prefs = _application_row(db, user)
    answers = dict(prefs.answers or {})
    for key, value in cleaned.items():
        if value is None:
            answers.pop(key, None)
        else:
            answers[key] = value
    prefs.answers = answers

    if "human_questions" in changes:
        raw = changes["human_questions"]
        if raw is None:
            prefs.human_questions = []
        else:
            prefs.human_questions = _validate_human_questions(raw)
    if "ai_applications_enabled" in changes:
        prefs.ai_applications_enabled = bool(changes["ai_applications_enabled"])
    if "user_information_all" in changes:
        text = changes["user_information_all"]
        if text is None:
            prefs.user_information_all = ""
        else:
            if not isinstance(text, str):
                raise ValueError("user_information_all must be text")
            prefs.user_information_all = text.strip()[:MAX_USER_INFO]
    if "ai_policy" in changes and changes["ai_policy"] is not None:
        deny = changes["ai_policy"].get("deny_label_contains") if isinstance(changes["ai_policy"], dict) else None
        if deny is not None:
            prefs.ai_policy = {"deny_label_contains": [str(x).strip().lower()[:64] for x in deny if str(x).strip()]}

    db.commit()
    return application_document(db, user)
