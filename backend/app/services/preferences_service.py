from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import uuid

from backend.app.core.errors import AppError
from backend.app.core.platform_defaults import DEFAULT_NOTIFICATIONS
from backend.app.models import ApplicationPreferences, SearchConfig, User, UserProfile
from backend.app.schemas.activity import NotificationPreferencesIn
from backend.app.services import platform_settings_service as ps
from backend.app.schemas.application_preferences import (
    DEFAULT_DENY,
    MAX_HUMAN_QUESTIONS,
    MAX_USER_INFO,
    HumanQuestionIn,
)
from backend.app.schemas.profile import ProfileIn, SearchConfigIn
from automation.qa_resolver import can_use_ai

from backend.app.services import application_ai_service
from backend.app.services.ai_service import ai_available
from backend.app.services.engine_fields import APPLICATION_FIELDS, validate_mapping

_QA_KEYS = frozenset({"human_questions", "ai_applications_enabled", "user_information_all", "ai_policy"})
_MAX_PENDING_FORM_QUESTIONS = 120
_ALLOWED_Q_TYPES = frozenset({"text", "textarea", "select", "radio", "checkbox", "number", "tel"})

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


def _upsert_human_rule(human: list, entry: dict) -> None:
    pattern = str(entry.get("pattern") or "").strip()
    for i, row in enumerate(human):
        if isinstance(row, dict) and str(row.get("pattern") or "").strip() == pattern:
            human[i] = entry
            return
    human.append(entry)


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


def _pending_label_key(label: str) -> str:
    return _clean_label_for_pattern(label).lower()


def _public_pending(items: list) -> list:
    out = []
    for row in items:
        if not isinstance(row, dict):
            continue
        if not row.get("needs_answer"):
            continue
        pub = {k: v for k, v in row.items() if k != "_key"}
        out.append(pub)
    return out


def _clean_label_for_pattern(label: str) -> str:
    text = (label or "").strip()
    for sep in (" [ ", " ["):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    if text.endswith(" ]"):
        text = text[:-2].strip()
    return text[:500] or "Unknown question"


def _human_rule_covers(label: str, human_questions: list) -> bool:
    from automation.qa_resolver import match_human_custom

    if not human_questions:
        return False
    cleaned = _clean_label_for_pattern(label)
    for candidate in (cleaned, (label or "").strip()):
        if not candidate:
            continue
        ans = match_human_custom(candidate, human_questions)
        if ans and str(ans).strip():
            return True
    return False


def _find_pending_item(pending: list, *, pid: str, label: str = "", question_type: str = "") -> dict | None:
    if pid:
        for p in pending:
            if str(p.get("id") or "") == pid:
                return p
    clean = _clean_label_for_pattern(label)
    if not clean:
        return None
    qtype = (question_type or "text").strip().lower()
    key = _pending_key(clean, qtype)
    for p in pending:
        if str(p.get("_key") or "") == key:
            return p
        if _clean_label_for_pattern(str(p.get("label") or "")) == clean:
            return p
    return None


def _persist_pending_and_human(prefs: ApplicationPreferences, pending: list, human: list) -> None:
    prefs.pending_form_questions = pending
    prefs.human_questions = human
    flag_modified(prefs, "pending_form_questions")
    flag_modified(prefs, "human_questions")


def _pending_still_needs_answer(*, engine_needs: bool, item: dict | None, human_questions: list) -> bool:
    if not engine_needs:
        return False
    if item and item.get("has_saved_rule"):
        return False
    if _human_rule_covers(str(item.get("label") if item else ""), human_questions):
        return False
    return True


def _notify_form_question_needed(db: Session, user_id: uuid.UUID, item: dict) -> None:
    from backend.app.services import notification_service

    label = str(item.get("label") or "Form question")
    job_title = str(item.get("job_title") or "")
    company = str(item.get("company") or "")
    message = f"LinkedIn asked: {label}"
    if job_title or company:
        where = " · ".join(x for x in (job_title, company) if x)
        message = f"{message} ({where})"
    notification_service.notify_event(
        db,
        user_id,
        "form_question",
        link="/app/automation?pending=1",
        variables={
            "question_label": label[:255],
            "job_title": job_title[:200],
            "company": company[:200],
            "message": message[:500],
        },
    )
    item["in_app_notified"] = True


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
    engine_needs = bool(event.get("needs_answer"))
    details = job_details or {}
    key = _pending_key(label, qtype)
    label_key = _pending_label_key(label)
    pending = list(prefs.pending_form_questions or [])
    human = list(prefs.human_questions or [])
    hit = next((p for p in pending if p.get("_key") == key), None)
    if hit is None and label_key:
        hit = next(
            (
                p
                for p in pending
                if _pending_label_key(str(p.get("label") or "")) == label_key
            ),
            None,
        )
        if hit is not None:
            hit["_key"] = key
            hit["question_type"] = qtype
    now = datetime.now(timezone.utc).isoformat()
    target: dict | None = hit
    if hit:
        hit["times_seen"] = int(hit.get("times_seen") or 1) + 1
        hit["last_seen_at"] = now
        hit["label"] = label
        still = _pending_still_needs_answer(
            engine_needs=engine_needs, item=hit, human_questions=human,
        )
        hit["needs_answer"] = still
        if not still:
            pending = [p for p in pending if p is not hit]
            target = None
        if options and not hit.get("options"):
            hit["options"] = options
    else:
        still_needs = _pending_still_needs_answer(
            engine_needs=engine_needs, item={"label": label}, human_questions=human,
        )
        if not still_needs:
            return
        target = {
            "id": str(uuid.uuid4()),
            "_key": key,
            "label": label,
            "question_type": qtype,
            "options": options,
            "job_id": str(event.get("job_id") or details.get("job_id") or "")[:64],
            "job_title": str(details.get("title") or "")[:200],
            "company": str(details.get("company") or "")[:200],
            "needs_answer": still_needs,
            "times_seen": 1,
            "first_seen_at": now,
            "last_seen_at": now,
        }
        pending.append(target)
    if len(pending) > _MAX_PENDING_FORM_QUESTIONS:
        pending = pending[-_MAX_PENDING_FORM_QUESTIONS:]
        if target and target not in pending:
            target = next((p for p in pending if p.get("_key") == key), target)
    if target and target.get("needs_answer") and not target.get("in_app_notified"):
        _notify_form_question_needed(db, user_id, target)
    prefs.pending_form_questions = pending
    flag_modified(prefs, "pending_form_questions")
    db.flush()


def resolve_pending_questions(db: Session, user: User, answers: list[dict]) -> dict:
    """Save answers for pending questions as custom human_questions and drop them from pending."""
    prefs = _application_row(db, user)
    pending = list(prefs.pending_form_questions or [])
    human = list(prefs.human_questions or [])
    keys_to_remove: set[str] = set()
    labels_to_remove: set[str] = set()
    saved = 0
    for row in answers:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        answer = str(row.get("answer") or "").strip()
        if not answer:
            continue
        row_label = str(row.get("label") or "")
        row_qtype = str(row.get("question_type") or "text").strip().lower()
        item = _find_pending_item(
            pending,
            pid=pid,
            label=row_label,
            question_type=row_qtype,
        )
        if item is None:
            pattern = _clean_label_for_pattern(row_label)
            if not pattern or pattern == "Unknown question":
                continue
            saved += 1
            qtype = row_qtype if row_qtype in _ALLOWED_Q_TYPES else "text"
            field_types = [qtype] if qtype in _ALLOWED_Q_TYPES else ["text", "textarea", "select", "radio"]
            _upsert_human_rule(
                human,
                HumanQuestionIn(
                    match="contains",
                    pattern=pattern,
                    answer=answer[:2000],
                    field_types=field_types,
                ).model_dump(),
            )
            keys_to_remove.add(_pending_key(pattern, str(qtype)))
            labels_to_remove.add(pattern.lower())
            continue
        saved += 1
        qtype = item.get("question_type") or "text"
        field_types = [qtype] if qtype in _ALLOWED_Q_TYPES else ["text", "textarea", "select", "radio"]
        pattern = _clean_label_for_pattern(item.get("label") or "")
        _upsert_human_rule(
            human,
            HumanQuestionIn(
                match="contains",
                pattern=pattern,
                answer=answer[:2000],
                field_types=field_types,
            ).model_dump(),
        )
        key = str(item.get("_key") or _pending_key(pattern, str(qtype)))
        keys_to_remove.add(key)
        labels_to_remove.add(pattern.lower())
    if answers and saved == 0:
        raise ValueError("Could not match any pending questions — refresh the page and try again.")
    if len(human) > MAX_HUMAN_QUESTIONS:
        raise ValueError(f"At most {MAX_HUMAN_QUESTIONS} custom questions are allowed")
    human = _validate_human_questions(human)

    def _drop(p: dict) -> bool:
        if str(p.get("_key") or "") in keys_to_remove:
            return True
        if _clean_label_for_pattern(str(p.get("label") or "")).lower() in labels_to_remove:
            return True
        if _human_rule_covers(str(p.get("label") or ""), human):
            return True
        return False

    pending = [p for p in pending if not _drop(p)]
    _persist_pending_and_human(prefs, pending, human)
    db.commit()
    return get_application(db, user)


_MAX_AI_SUGGEST_BATCH = 25


def suggest_pending_ai_answers(db: Session, user: User, *, ids: list[str] | None = None) -> dict:
    """Use platform AI (profile + default resume) to draft answers for pending LinkedIn questions."""
    if not ai_available(db, feature="applications") and not ai_available(db, feature="resume"):
        raise AppError("AI_DISABLED", "Platform AI is not enabled for applications.", 503)
    doc = application_document(db, user)
    policy = doc.get("ai_policy") or {}
    pending = [p for p in (doc.get("pending_form_questions") or []) if p.get("needs_answer")]
    if ids is not None:
        wanted = {str(i).strip() for i in ids if str(i).strip()}
        pending = [p for p in pending if p.get("id") in wanted]
    if len(pending) > _MAX_AI_SUGGEST_BATCH:
        raise ValueError(f"At most {_MAX_AI_SUGGEST_BATCH} questions per request")
    suggestions: list[dict] = []
    skipped: list[dict] = []
    for item in pending:
        pid = str(item.get("id") or "")
        label = str(item.get("label") or "")
        qtype = str(item.get("question_type") or "text").lower()
        options = item.get("options") if isinstance(item.get("options"), list) else []
        from automation.answer_format import infer_answer_format

        ai_qtype = "number" if infer_answer_format(label, qtype) == "number" else qtype
        if not can_use_ai(label.lower(), ai_qtype, policy):
            skipped.append({"id": pid, "reason": "not_eligible"})
            continue
        try:
            answer = application_ai_service.answer_application_question(
                db,
                user.id,
                question=label,
                question_type=qtype,
                options=[str(o) for o in options],
                job_title=str(item.get("job_title") or ""),
                company=str(item.get("company") or ""),
            )
        except AppError as exc:
            skipped.append({"id": pid, "reason": exc.code})
            continue
        if answer:
            suggestions.append({"id": pid, "answer": answer[:2000]})
        else:
            skipped.append({"id": pid, "reason": "empty"})
    return {"suggestions": suggestions, "skipped": skipped}


def reconcile_pending_form_questions(db: Session, user: User) -> None:
    """Drop pending rows that already have a custom rule (fixes legacy re-opened items)."""
    prefs = _application_row(db, user)
    pending = list(prefs.pending_form_questions or [])
    human = list(prefs.human_questions or [])
    by_label: dict[str, dict] = {}
    changed = False
    for p in pending:
        if not isinstance(p, dict):
            changed = True
            continue
        if not p.get("id"):
            p["id"] = str(uuid.uuid4())
            changed = True
        if not p.get("needs_answer") or p.get("has_saved_rule") or _human_rule_covers(str(p.get("label") or ""), human):
            changed = True
            continue
        qtype = str(p.get("question_type") or "text")
        key = str(p.get("_key") or _pending_key(str(p.get("label") or ""), qtype))
        p["_key"] = key
        lk = _pending_label_key(str(p.get("label") or ""))
        if not lk:
            changed = True
            continue
        prev = by_label.get(lk)
        if prev is not None:
            changed = True
        if prev is None or str(p.get("last_seen_at") or "") >= str(prev.get("last_seen_at") or ""):
            by_label[lk] = p
    kept = list(by_label.values())
    if changed or len(kept) != len(pending):
        prefs.pending_form_questions = kept
        flag_modified(prefs, "pending_form_questions")
        db.commit()


def get_application(db: Session, user: User) -> dict:
    reconcile_pending_form_questions(db, user)
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
    return get_application(db, user)


def _ensure_profile(db: Session, user: User) -> UserProfile:
    if user.profile is None:
        user.profile = UserProfile(user_id=user.id)
        db.add(user.profile)
        db.flush()
    return user.profile


def get_notification_preferences(db: Session, user: User) -> dict:
    profile = _ensure_profile(db, user)
    stored = profile.notification_email or {}
    platform = ps.get_notification_prefs(db)
    types: dict = {}
    for key, meta in platform.items():
        types[key] = {
            "email": bool(stored.get(key, True)),
            "label": meta.get("label", key),
            "description": meta.get("description", ""),
        }
    return {"types": types}


def update_notification_preferences(db: Session, user: User, payload: NotificationPreferencesIn) -> dict:
    profile = _ensure_profile(db, user)
    stored = dict(profile.notification_email or {})
    for key, value in payload.types.items():
        if key not in DEFAULT_NOTIFICATIONS:
            raise AppError("VALIDATION_ERROR", f"Unknown notification type: {key}", 422)
        stored[key] = value.email
    profile.notification_email = stored
    db.commit()
    return get_notification_preferences(db, user)
