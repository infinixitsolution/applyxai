'''
The engine's hooks for the ApplyXAI agent, exercised through runAiBot.py's real functions
with a stubbed browser: outcome events, the CSV history round trip, and a clean stop.

License: MIT  (https://opensource.org/license/mit)
'''

import json
import sys
import types
from datetime import datetime

import pytest

from automation import csv_import, events as ev
from modules import run_hooks


@pytest.fixture(scope="module")
def bot():
    '''Import runAiBot with a stubbed browser session, so importing it never opens Chrome.'''
    fake_chrome = types.ModuleType("modules.open_chrome")
    fake_chrome.options = fake_chrome.driver = fake_chrome.actions = fake_chrome.wait = None
    sys.modules["modules.open_chrome"] = fake_chrome
    import runAiBot
    return runAiBot


@pytest.fixture
def sink(tmp_path, monkeypatch, bot):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv(run_hooks.EVENTS_ENV, str(path))
    monkeypatch.setattr(bot, "file_name", str(tmp_path / "applied.csv"))
    monkeypatch.setattr(bot, "failed_file_name", str(tmp_path / "failed.csv"))
    return path


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def submit(bot, job_id, application_link="Easy Applied"):
    bot.submitted_jobs(job_id, "Python Developer", "Acme", "Pune, India", "Hybrid", "Build APIs.", 2, "Needs an AI",
                       "Unknown", "Unknown", "resume.pdf", False, datetime(2026, 9, 1, 10, 0), datetime(2026, 9, 2, 11, 30),
                       f"https://www.linkedin.com/jobs/view/{job_id}", application_link, {("Phone?", "123", "text", "")},
                       "In Development")


def test_submitted_jobs_emits_applied_and_still_writes_the_csv(bot, sink):
    submit(bot, "4001")
    (event,) = read(sink)
    assert event["event"] == "applied" and event["job_id"] == "4001"
    assert (event["title"], event["company"], event["work_style"]) == ("Python Developer", "Acme", "Hybrid")
    assert datetime.fromisoformat(event["date_applied"]).tzinfo is not None
    assert "questions_list" not in event and "resume" not in event        # screening answers stay local
    assert "4001" in open(bot.file_name, encoding="utf-8").read()


def test_external_application_is_its_own_event(bot, sink):
    submit(bot, "4002", application_link="https://careers.example.com/apply/9")
    assert read(sink)[0]["event"] == "external"


def test_failed_job_distinguishes_skips_from_failures(bot, sink):
    bot.failed_job("5001", "https://www.linkedin.com/jobs/view/5001", "Pending", "Unknown",
                   "Found Blacklisted words in About Company", ValueError("staffing agency"), "Skipped", "Not Available")
    bot.failed_job("5002", "https://www.linkedin.com/jobs/view/5002", "resume.pdf", "Unknown",
                   "Problem in Easy Applying", RuntimeError("Submit button missing"), "Easy Applied", "shot.png")
    skipped, failed = read(sink)
    assert skipped["event"] == "skipped" and skipped["reason"] == "Found Blacklisted words in About Company"
    assert failed["event"] == "failed" and failed["detail"] == "Submit button missing"


def test_engine_csvs_import_as_the_same_events(bot, sink):
    submit(bot, "6001")
    submit(bot, "6002", application_link="https://careers.example.com/x")
    bot.failed_job("6003", "https://www.linkedin.com/jobs/view/6003", "Pending", "Unknown",
                   "Problem in Easy Applying", RuntimeError("boom"), "Easy Applied", "Not Available")

    imported = csv_import.read_history(bot.file_name, bot.failed_file_name)
    assert [(e["event"], e["job_id"]) for e in imported] == [("failed", "6003"), ("applied", "6001"), ("external", "6002")]
    applied = imported[1]
    assert applied["title"] == "Python Developer" and applied["company"] == "Acme"
    assert ev.parse_time(applied["date_applied"]) is not None
    assert all(ev.validate_event(e) for e in imported)


class FakeDriver:
    window_handles = ["tab-1"]
    current_window_handle = "tab-1"
    current_url = "https://www.linkedin.com/feed/"

    def get(self, url):
        pass

    class switch_to:
        @staticmethod
        def window(handle):
            pass

    def quit(self):
        self.closed = True


def test_stop_request_ends_main_cleanly_with_a_final_event(bot, sink, monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(bot, "driver", driver)
    monkeypatch.setattr(bot, "validate_config", lambda: True)
    monkeypatch.setattr(bot, "is_logged_in_LN", lambda: True)
    monkeypatch.setattr(bot, "use_AI", False)
    monkeypatch.setattr(bot, "run_non_stop", False)
    monkeypatch.setattr(bot, "print_lg", lambda *a, **k: None)
    monkeypatch.setattr(bot.pyautogui, "alert", lambda *a, **k: None)

    def stopped(total_runs):
        raise run_hooks.StopRequested()
    monkeypatch.setattr(bot, "run", stopped)

    bot.main()

    kinds = [e["event"] for e in read(sink)]
    assert kinds[0] == "run_started" and kinds[-1] == "run_finished"
    final = read(sink)[-1]
    assert final["stopped"] is True and final["error"] == ""
    assert driver.closed
