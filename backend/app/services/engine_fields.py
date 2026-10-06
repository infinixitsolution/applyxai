"""
Validation for engine settings the SaaS stores on a user's behalf.

Field metadata (type, label, help) comes from config_schema.py; allowed values and integer
minimums come from automation/options.py (mirrors modules/validator.py). Anything the
engine would reject at run time is rejected here, at save time.
"""

import config_schema
from automation.options import ENGINE_INT_MINIMUMS, ENGINE_OPTIONS

MAX_TEXT = 1_000
MAX_TEXTAREA = 10_000
MAX_LIST_ITEMS = 100
MAX_LIST_ITEM = 500

# Search settings with dedicated columns on search_configs (engine name -> column).
SEARCH_COLUMNS = {
    "search_terms": "keywords",
    "search_location": "location",
    "easy_apply_only": "easy_apply_only",
    "experience_level": "experience_level",
    "job_type": "job_type",
    "on_site": "on_site",
    "companies": "companies",
    "date_posted": "date_posted",
    "sort_by": "sort_by",
}
# Represented as salary_min / salary_max instead of LinkedIn's "$80,000+" buckets.
_SEARCH_NOT_STORED = {"salary"}

# Application answers that live elsewhere in the SaaS, or that only make sense on the
# machine running the browser (the user's desktop agent).
_APPLICATION_EXCLUDED = {
    "first_name", "last_name", "phone_number",            # users / user_profiles
    "linkedin_headline", "linkedin_summary",               # user_profiles.headline / summary
    "default_resume_path",                                 # resumes (default resume)
    "auto_manage_driver", "safe_mode", "log_level", "keep_screen_awake",
}
_APPLICATION_SECTIONS = {"Profile", "Run settings"}


def _fields():
    return list(config_schema.iter_fields())


SEARCH_EXTRA_FIELDS = {
    f["key"]: f for f in _fields()
    if f["config_module"] == "search" and f["key"] not in SEARCH_COLUMNS and f["key"] not in _SEARCH_NOT_STORED
}
APPLICATION_FIELDS = {
    f["key"]: f for f in _fields()
    if f["section"] in _APPLICATION_SECTIONS and f["key"] not in _APPLICATION_EXCLUDED
}


def allowed_values(field: dict) -> list | None:
    return ENGINE_OPTIONS.get(field["key"]) or field.get("options")


def clean_str_list(values, *, max_items: int = MAX_LIST_ITEMS, max_len: int = MAX_LIST_ITEM,
                   label: str = "value") -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
    seen, cleaned = set(), []
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"every {label} must be text")
        item = item.strip()
        if not item or item.lower() in seen:
            continue
        if len(item) > max_len:
            raise ValueError(f"each {label} must be at most {max_len} characters")
        seen.add(item.lower())
        cleaned.append(item)
    if len(cleaned) > max_items:
        raise ValueError(f"at most {max_items} entries are allowed for {label}")
    return cleaned


def validate_value(field: dict, value):
    """Return the cleaned value, or raise ValueError with a user-facing message."""
    key, ftype, label = field["key"], field["type"], field["label"]
    options = allowed_values(field)

    if ftype == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{label} must be true or false")
        return value

    if ftype == "number":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be a whole number")
        minimum = ENGINE_INT_MINIMUMS.get(key, 0)
        if value < minimum:
            raise ValueError(f"{label} must be at least {minimum}")
        return value

    if ftype in ("text", "textarea", "password", "select"):
        if not isinstance(value, str):
            raise ValueError(f"{label} must be text")
        value = value.strip()
        if ftype == "select" or (options and key in ENGINE_OPTIONS):
            if value not in options:
                raise ValueError(f"Invalid {label.lower()} '{value}'. Allowed: {', '.join(repr(o) for o in options)}")
            return value
        limit = MAX_TEXTAREA if ftype == "textarea" else MAX_TEXT
        if len(value) > limit:
            raise ValueError(f"{label} must be at most {limit} characters")
        return value

    if ftype == "list":
        cleaned = clean_str_list(value, label=label.lower())
        if key in ENGINE_OPTIONS:
            bad = [v for v in cleaned if v not in ENGINE_OPTIONS[key]]
            if bad:
                raise ValueError(f"Invalid {label.lower()} {bad}. Allowed: {', '.join(ENGINE_OPTIONS[key])}")
        return cleaned

    raise ValueError(f"{label} has an unsupported type")


def validate_mapping(fields: dict[str, dict], payload: dict, *, allow_null: bool = False) -> dict:
    """Validate {engine_key: value}; unknown keys are errors. With allow_null, None means 'unset'."""
    if not isinstance(payload, dict):
        raise ValueError("expected an object")
    errors, cleaned = [], {}
    for key, value in payload.items():
        field = fields.get(key)
        if field is None:
            errors.append({"field": key, "message": "Unknown setting"})
            continue
        if value is None and allow_null:
            cleaned[key] = None
            continue
        try:
            cleaned[key] = validate_value(field, value)
        except ValueError as exc:
            errors.append({"field": key, "message": str(exc)})
    if errors:
        raise FieldErrors(errors)
    return cleaned


def describe(fields: dict[str, dict]) -> list[dict]:
    """Public metadata for building forms in the frontend."""
    out = []
    for key, f in fields.items():
        item = {"key": key, "label": f["label"], "type": f["type"], "help": f["help"], "section": f["section"],
                "advanced": bool(f.get("advanced"))}
        options = allowed_values(f)
        if options is not None and (f["type"] == "select" or key in ENGINE_OPTIONS):
            item["options"] = options
        out.append(item)
    return out


class FieldErrors(ValueError):
    def __init__(self, errors: list[dict]):
        super().__init__(errors[0]["message"] if len(errors) == 1 else "Invalid settings")
        self.errors = errors
