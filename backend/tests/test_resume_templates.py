from backend.app.services.resume_templates import DEFAULT_TEMPLATE_ID, list_templates, normalize_template_id


def test_ten_templates():
    items = list_templates()
    assert len(items) == 10
    assert all(t.get("layout") and t.get("layout_label") for t in items)
    assert {t["id"] for t in items} == {
        "classic",
        "modern",
        "minimal",
        "professional",
        "compact",
        "elegant",
        "bold",
        "tech",
        "creative",
        "executive",
    }


def test_normalize_defaults():
    assert normalize_template_id(None) == DEFAULT_TEMPLATE_ID
    assert normalize_template_id("  Modern ") == "modern"
