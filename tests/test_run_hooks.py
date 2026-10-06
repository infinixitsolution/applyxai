'''
Tests for modules/run_hooks.py: the optional event sink, control file, and profile hooks
the ApplyXAI agent uses. Without their environment variables every hook must be a no-op,
because the classic workflow never sets them.

License: MIT  (https://opensource.org/license/mit)
'''

import json
from datetime import datetime

import pytest

from modules import run_hooks


@pytest.fixture(autouse=True)
def no_supervisor(monkeypatch):
    for name in (run_hooks.EVENTS_ENV, run_hooks.CONTROL_ENV, run_hooks.PROFILE_ENV, run_hooks.MAX_APPLIED_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(run_hooks, "_applied", 0)


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_hooks_do_nothing_without_a_supervisor(tmp_path):
    run_hooks.emit("applied", job_id="1")
    run_hooks.checkpoint(sleep=lambda s: pytest.fail("must not wait"))
    assert run_hooks.profile_dir() is None
    assert list(tmp_path.iterdir()) == []


def test_emit_appends_one_json_line_per_event(tmp_path, monkeypatch):
    sink = tmp_path / "events.jsonl"
    monkeypatch.setenv(run_hooks.EVENTS_ENV, str(sink))
    run_hooks.emit("job_started", job_id="42", title="Dev")
    run_hooks.emit("applied", job_id="42", reposted=False, skills={"Python"}, date_applied=datetime(2026, 1, 2, 3, 4, 5))

    first, second = read(sink)
    assert first["event"] == "job_started" and first["job_id"] == "42" and first["title"] == "Dev"
    assert first["ts"].endswith("+00:00")
    assert second["skills"] == ["Python"] and second["reposted"] is False
    # Naive engine times get this machine's offset, so they can't be misread as UTC later.
    assert datetime.fromisoformat(second["date_applied"]).tzinfo is not None


def test_emit_truncates_huge_text_and_never_raises(tmp_path, monkeypatch):
    sink = tmp_path / "events.jsonl"
    monkeypatch.setenv(run_hooks.EVENTS_ENV, str(sink))
    run_hooks.emit("applied", job_id="1", description="x" * (run_hooks.MAX_TEXT + 500))
    assert read(sink)[0]["description"].endswith("[TRUNCATED]")

    monkeypatch.setenv(run_hooks.EVENTS_ENV, str(tmp_path))      # a directory: open() fails
    run_hooks.emit("applied", job_id="1")                         # ...and that's swallowed


def test_checkpoint_stop_raises_something_except_exception_cannot_catch(tmp_path, monkeypatch):
    control = tmp_path / "control"
    control.write_text("stop", encoding="utf-8")
    monkeypatch.setenv(run_hooks.CONTROL_ENV, str(control))

    with pytest.raises(run_hooks.StopRequested):
        try:
            run_hooks.checkpoint()
        except Exception:                      # the engine's broad handlers look like this
            pytest.fail("a stop request was swallowed by `except Exception`")


@pytest.mark.parametrize("state", ["run", "", "unexpected"])
def test_checkpoint_continues_when_not_paused_or_stopped(tmp_path, monkeypatch, state):
    control = tmp_path / "control"
    control.write_text(state, encoding="utf-8")
    monkeypatch.setenv(run_hooks.CONTROL_ENV, str(control))
    run_hooks.checkpoint(sleep=lambda s: pytest.fail("must not wait"))


def test_checkpoint_waits_while_paused_then_resumes(tmp_path, monkeypatch):
    control, sink = tmp_path / "control", tmp_path / "events.jsonl"
    control.write_text("pause", encoding="utf-8")
    monkeypatch.setenv(run_hooks.CONTROL_ENV, str(control))
    monkeypatch.setenv(run_hooks.EVENTS_ENV, str(sink))
    waits = []

    def fake_sleep(seconds):
        waits.append(seconds)
        if len(waits) == 3:
            control.write_text("run", encoding="utf-8")

    run_hooks.checkpoint(sleep=fake_sleep)
    assert len(waits) == 3
    assert [e["event"] for e in read(sink)] == ["paused", "resumed"]


def test_stop_while_paused_raises(tmp_path, monkeypatch):
    control = tmp_path / "control"
    control.write_text("pause", encoding="utf-8")
    monkeypatch.setenv(run_hooks.CONTROL_ENV, str(control))
    with pytest.raises(run_hooks.StopRequested):
        run_hooks.checkpoint(sleep=lambda s: control.write_text("stop", encoding="utf-8"))


def test_the_application_cap_stops_at_the_next_checkpoint(tmp_path, monkeypatch):
    control, sink = tmp_path / "control", tmp_path / "events.jsonl"
    control.write_text("run", encoding="utf-8")
    monkeypatch.setenv(run_hooks.CONTROL_ENV, str(control))
    monkeypatch.setenv(run_hooks.EVENTS_ENV, str(sink))
    monkeypatch.setenv(run_hooks.MAX_APPLIED_ENV, "2")
    run_hooks.emit("applied", job_id="1")
    run_hooks.emit("skipped", job_id="2")
    run_hooks.checkpoint()
    run_hooks.emit("applied", job_id="3")
    with pytest.raises(run_hooks.StopRequested):
        run_hooks.checkpoint()
    assert read(sink)[-1]["event"] == "limit_reached" and read(sink)[-1]["applied"] == 2


def test_a_zero_cap_stops_before_the_first_job_and_a_bad_value_is_ignored(tmp_path, monkeypatch):
    control = tmp_path / "control"
    control.write_text("run", encoding="utf-8")
    monkeypatch.setenv(run_hooks.CONTROL_ENV, str(control))
    monkeypatch.setenv(run_hooks.MAX_APPLIED_ENV, "lots")
    run_hooks.checkpoint()
    monkeypatch.setenv(run_hooks.MAX_APPLIED_ENV, "0")
    with pytest.raises(run_hooks.StopRequested):
        run_hooks.checkpoint()


def test_profile_dir_is_created(tmp_path, monkeypatch):
    target = tmp_path / "user" / "profile"
    monkeypatch.setenv(run_hooks.PROFILE_ENV, str(target))
    assert run_hooks.profile_dir() == str(target) and target.is_dir()
