"""Unit tests for LinkedIn profile sync browser helpers (no real browser)."""

from automation.linkedin_profile import browser as lp_browser


def test_should_write_respects_fill_empty_and_overwrite():
    assert lp_browser._should_write("", "New headline", fill_empty=True, overwrite=False)
    assert not lp_browser._should_write("Existing", "New", fill_empty=True, overwrite=False)
    assert lp_browser._should_write("Existing", "New", fill_empty=True, overwrite=True)
    assert not lp_browser._should_write("x", "  ", fill_empty=True, overwrite=True)


def test_apply_section_skips_unknown_section():
    class DummyDriver:
        def get(self, url):
            raise AssertionError("should not navigate")

    assert lp_browser.apply_section(DummyDriver(), "certifications", {}, {}) == "skipped"


def test_photo_skips_without_file(tmp_path):
    class DummyDriver:
        def get(self, url):
            pass

    assert lp_browser.apply_section(
        DummyDriver(), "photo", {"has_photo": True}, {}, photo_path=str(tmp_path / "missing.jpg"),
    ) == "skipped"
