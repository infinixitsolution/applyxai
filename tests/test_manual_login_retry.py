"""manual_login_retry waits on Chrome login without requiring Tk dialogs."""

from modules.helpers import manual_login_retry


def test_supervised_login_wait_polls_until_logged_in(monkeypatch):
    monkeypatch.setenv("APPLYXAI_RUN_CONFIG", "config.json")
    monkeypatch.setattr("modules.helpers.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("modules.helpers.print_lg", lambda *_a, **_k: None)
    states = [False, False, True]
    manual_login_retry(lambda: states.pop(0) if states else True, poll_seconds=0, max_wait_seconds=10)
    assert states == []


def test_supervised_login_wait_times_out(monkeypatch):
    monkeypatch.setenv("APPLYXAI_CONTROL_FILE", "control")
    monkeypatch.setattr("modules.helpers.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("modules.helpers.print_lg", lambda *_a, **_k: None)
    from datetime import datetime, timedelta

    start = datetime(2026, 1, 1, 12, 0, 0)
    ticks = {"n": 0}

    class FakeDateTime:
        @classmethod
        def now(cls):
            ticks["n"] += 1
            return start + timedelta(seconds=ticks["n"] * 100)

    monkeypatch.setattr("modules.helpers.datetime", FakeDateTime)
    manual_login_retry(lambda: False, poll_seconds=0, max_wait_seconds=10)
    assert ticks["n"] >= 1
