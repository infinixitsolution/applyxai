"""Checkpoint / captcha pages block that job source and emit login_required."""

import types

from automation.sources.challenges import challenge_reason
from automation.sources import naukri


class FakeEl:
    def __init__(self, *, text="", src="", title=""):
        self.text = text
        self._src = src
        self._title = title

    def get_attribute(self, name):
        if name == "src":
            return self._src
        if name == "title":
            return self._title
        return ""


class FakeDriver:
    def __init__(self, url="", *, frames=None, body=""):
        self.current_url = url
        self._frames = frames or []
        self._body = FakeEl(text=body)

    def get(self, url):
        self.current_url = url

    def find_elements(self, _by, selector):
        if "iframe" in selector:
            return self._frames
        return []

    def find_element(self, _by, selector):
        if selector == "body":
            return self._body
        raise RuntimeError(selector)


def test_linkedin_checkpoint_url_is_a_challenge():
    reason = challenge_reason(
        FakeDriver("https://www.linkedin.com/checkpoint/challenge/verify"),
        platform="LinkedIn",
    )
    assert reason
    assert "LinkedIn" in reason
    assert "security check" in reason.lower()


def test_naukri_captcha_url_is_a_challenge():
    reason = challenge_reason(
        FakeDriver("https://www.naukri.com/mnj/captcha"),
        platform="Naukri",
    )
    assert reason and "Naukri" in reason


def test_recaptcha_iframe_is_a_challenge():
    driver = FakeDriver(
        "https://www.linkedin.com/jobs/search/?keywords=python",
        frames=[FakeEl(src="https://www.google.com/recaptcha/api2/anchor", title="reCAPTCHA")],
    )
    assert challenge_reason(driver, platform="LinkedIn")


def test_plain_job_search_is_not_a_challenge():
    driver = FakeDriver(
        "https://www.linkedin.com/jobs/search/?keywords=python",
        body="Easy Apply Senior Analyst Bengaluru",
    )
    assert challenge_reason(driver, platform="LinkedIn") is None


def test_naukri_apply_batch_blocks_and_emits_login_required(monkeypatch):
    emitted = []
    fake = types.SimpleNamespace(
        buffer=lambda *a, **k: None,
        run_hooks=types.SimpleNamespace(
            emit=lambda kind, **kw: emitted.append((kind, kw)),
            checkpoint=lambda: None,
        ),
        get_applied_job_ids=lambda: set(),
        years_of_experience=0,
        current_experience=0,
        date_posted="week",
    )
    monkeypatch.setitem(__import__("sys").modules, "runAiBot", fake)
    monkeypatch.setattr(naukri, "ensure_login", lambda _d: True)

    driver = FakeDriver("https://www.naukri.com/checkpoint/captcha")
    driver.get = lambda _url: None

    status, submitted, reason = naukri.apply_batch(
        driver, ["python"], "Bengaluru", max_successful=5, cursor={},
    )
    assert status == "blocked"
    assert submitted == 0
    assert "security check" in reason.lower()
    assert ("login_required", {"platform": "naukri"}) in emitted
