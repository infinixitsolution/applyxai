"""Naukri apply-loop honesty: chat close is not success; Apply is not Submit."""

import sys
import types

import pytest

from automation.sources import naukri
from automation.sources.naukri_links import (
    classify_apply,
    is_submit_control,
    job_age_days,
    listing_skip_reason,
    search_url,
)


@pytest.fixture(autouse=True)
def stub_run_aibot(monkeypatch):
    existing = sys.modules.get("runAiBot")
    if existing is None:
        fake = types.ModuleType("runAiBot")
        fake.buffer = lambda *a, **k: None
        fake.run_hooks = types.SimpleNamespace(emit=lambda *a, **k: None)
        monkeypatch.setitem(sys.modules, "runAiBot", fake)
    else:
        monkeypatch.setattr(existing, "buffer", lambda *a, **k: None, raising=False)


class FakeEl:
    def __init__(self, text, *, displayed=True):
        self.text = text
        self._displayed = displayed
        self.clicked = False

    def is_displayed(self):
        return self._displayed

    def click(self):
        self.clicked = True


def test_submit_control_never_treats_apply_as_submit():
    assert is_submit_control("Submit") is True
    assert is_submit_control("Send") is True
    assert is_submit_control("Save and continue") is True
    assert is_submit_control("Apply") is False
    assert is_submit_control("Apply now") is False
    assert is_submit_control("Apply on company site") is False


def test_pick_apply_uses_classify_apply_and_skips_filters(monkeypatch):
    apply_btn = FakeEl("Apply")
    company = FakeEl("Apply on company site")
    filters = FakeEl("Apply filters")
    monkeypatch.setattr(naukri, "_visible_controls", lambda _d: [filters, apply_btn, company])
    kind, button = naukri._pick_apply(object())
    assert kind == "onsite"
    assert button is apply_btn
    assert classify_apply("Apply on company site", False) == "external"


def test_submit_drawer_does_not_click_apply(monkeypatch):
    apply_btn = FakeEl("Apply")
    monkeypatch.setattr(naukri, "_visible_controls", lambda _d: [apply_btn])
    assert naukri._submit_drawer(object(), dry_run=False) is False
    assert apply_btn.clicked is False


def test_submit_drawer_clicks_submit_only(monkeypatch):
    apply_btn = FakeEl("Apply")
    submit_btn = FakeEl("Submit")
    monkeypatch.setattr(naukri, "_visible_controls", lambda _d: [apply_btn, submit_btn])
    assert naukri._submit_drawer(object(), dry_run=False) is True
    assert apply_btn.clicked is False
    assert submit_btn.clicked is True


def test_walk_apply_chat_closed_without_success_is_failure(monkeypatch):
    monkeypatch.setattr(naukri, "_chat_open", lambda _d: True)
    monkeypatch.setattr(naukri, "_application_sent", lambda _d: False)
    monkeypatch.setattr(naukri, "_latest_question", lambda _d: "Are you a fresher or experienced?")
    monkeypatch.setattr(naukri, "_chat_options", lambda _d: [(FakeEl("Fresher"), "Fresher")])
    monkeypatch.setattr(naukri, "_chat_answer", lambda *a, **k: "Fresher")
    monkeypatch.setattr(naukri, "_click_chat_choice", lambda *a, **k: True)
    monkeypatch.setattr(naukri, "_record_chat_answer", lambda *a, **k: None)
    monkeypatch.setattr(naukri, "_wait_for_next_question", lambda *a, **k: "__closed__")
    monkeypatch.setattr("runAiBot.buffer", lambda *a, **k: None, raising=False)

    sent, reason = naukri._walk_apply_chat(
        object(), description="", title="Role", company="Co", resume_path="",
    )
    assert sent is False
    assert "closed" in reason.lower()


def test_walk_apply_chat_sent_phrase_is_success(monkeypatch):
    monkeypatch.setattr(naukri, "_chat_open", lambda _d: True)
    monkeypatch.setattr(naukri, "_application_sent", lambda _d: True)
    monkeypatch.setattr("runAiBot.buffer", lambda *a, **k: None, raising=False)
    sent, reason = naukri._walk_apply_chat(
        object(), description="", title="Role", company="Co", resume_path="",
    )
    assert sent is True
    assert reason == ""


def test_walk_apply_chat_no_drawer_is_not_submitted(monkeypatch):
    monkeypatch.setattr(naukri, "_chat_open", lambda _d: False)
    monkeypatch.setattr("runAiBot.buffer", lambda *a, **k: None, raising=False)
    sent, reason = naukri._walk_apply_chat(
        object(), description="", title="Role", company="Co", resume_path="",
    )
    assert sent is False
    assert reason == ""


def test_listing_skip_reason_matches_company_and_phrase():
    assert listing_skip_reason("Python", "Crossover", "", company_bad_words=["Crossover"])
    assert listing_skip_reason("PHP Developer", "Acme", "Need PHP", bad_words=["PHP"])
    assert listing_skip_reason("Python", "Acme", "Django work", bad_words=["PHP"]) == ""


def test_search_url_adds_date_and_experience():
    assert job_age_days("Past week") == "7"
    url = search_url("Python Developer", "Bengaluru", date_posted="Past week", experience_years=0)
    assert "k=Python+Developer" in url
    assert "l=Bengaluru" in url
    assert "jobAge=7" in url
    assert "experience=0" in url
