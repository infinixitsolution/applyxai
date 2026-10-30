"""Idle wake and immediate event flush so the web app stays in sync with Desktop."""

from pathlib import Path

from agent.supervisor import _FLUSH_NOW, Supervisor
from automation import events as ev


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class IdlePoller:
    def poll(self):
        return {"run": None}


def test_flush_now_includes_login_blocked_and_profile_sync():
    assert ev.LOGIN_REQUIRED in _FLUSH_NOW
    assert ev.SOURCE_BLOCKED in _FLUSH_NOW
    assert ev.PROFILE_EVENTS <= _FLUSH_NOW


def test_nudge_skips_the_idle_wait(tmp_path: Path):
    clock = Clock()
    sup = Supervisor(IdlePoller(), tmp_path, "u", sleep=clock.sleep, clock=clock)
    sup.nudge()
    sup._idle_wait(5)
    assert clock.t == 0


def test_idle_wait_without_nudge_uses_the_full_delay(tmp_path: Path):
    clock = Clock()
    sup = Supervisor(IdlePoller(), tmp_path, "u", sleep=clock.sleep, clock=clock)
    sup._idle_wait(5)
    assert clock.t >= 5


def test_agent_latest_version_follows_repo_version():
    from backend.app.core.config import _agent_latest_version

    version = Path(__file__).resolve().parents[1].joinpath("VERSION").read_text(encoding="utf-8").strip().splitlines()[0].strip()
    assert _agent_latest_version() == version
