'''
automation/runner.py with a fake subprocess: workspace layout, environment, control
file, event reading, and the stop-then-kill fallback. No real engine is started.

License: MIT  (https://opensource.org/license/mit)
'''

import json
import subprocess

import pytest

from automation import events as ev
from automation.runner import ENGINE_ROOT, ENGINE_SCRIPT, EngineRun, RunnerError, Workspace


class FakeProcess:
    def __init__(self, args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.pid = 4242
        self.code = None
        self.exit_on_wait = True

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        if not self.exit_on_wait:
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.code = 0
        return 0

    def terminate(self):
        self.code = -15

    def kill(self):
        self.code = -9


@pytest.fixture
def launched():
    procs = []

    def popen(args, **kwargs):
        procs.append(FakeProcess(args, **kwargs))
        return procs[-1]
    return procs, popen


def test_start_lays_out_the_workspace_and_points_the_engine_at_it(tmp_path, launched):
    procs, popen = launched
    ws = Workspace(tmp_path / "alice")
    run = EngineRun(ws, "run-1", python="python-exe", popen=popen)
    run.start({"search": {"search_terms": ["Dev"]}})

    (proc,) = procs
    assert proc.args == ["python-exe", str(ENGINE_SCRIPT)]
    assert proc.kwargs["cwd"] == str(ENGINE_ROOT)
    env = proc.kwargs["env"]
    assert env["APPLYXAI_RUN_CONFIG"] == str(run.config_path)
    assert env["APPLYXAI_EVENTS_FILE"] == str(run.events_path)
    assert env["APPLYXAI_CONTROL_FILE"] == str(run.control_path)
    assert env["APPLYXAI_PROFILE_DIR"] == str(ws.profile_dir)
    assert json.loads(run.config_path.read_text(encoding="utf-8")) == {"search": {"search_terms": ["Dev"]}}
    assert run.control_state() == "run" and run.events_path.exists()
    assert ws.profile_dir.is_dir() and ws.history_dir.is_dir()
    assert run.running

    with pytest.raises(RunnerError):
        run.start({})


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", "x" * 65, "run 1"])
def test_run_ids_cannot_escape_the_workspace(tmp_path, bad):
    with pytest.raises(RunnerError):
        Workspace(tmp_path).run_dir(bad)


def test_pause_resume_and_stop_write_the_control_file(tmp_path, launched):
    procs, popen = launched
    run = EngineRun(Workspace(tmp_path), "r", popen=popen)
    run.start({})
    run.pause()
    assert run.control_state() == "pause"
    run.resume()
    assert run.control_state() == "run"
    assert run.stop(timeout=1) == 0
    assert run.control_state() == "stop" and not run.running


def test_stop_kills_the_engine_when_it_does_not_exit_in_time(tmp_path, launched, monkeypatch):
    procs, popen = launched
    run = EngineRun(Workspace(tmp_path), "r", popen=popen)
    run.start({})
    procs[0].exit_on_wait = False
    killed = []
    monkeypatch.setattr(run, "kill", lambda: killed.append(True) or setattr(procs[0], "code", -9))
    assert run.stop(timeout=0.01) == -9
    assert killed


def test_new_events_returns_each_event_once_and_waits_for_whole_lines(tmp_path, launched):
    procs, popen = launched
    run = EngineRun(Workspace(tmp_path), "r", popen=popen)
    run.start({})
    with open(run.events_path, "a", encoding="utf-8") as sink:
        sink.write(json.dumps({"event": "run_started", "ts": "2026-10-07T00:00:00+00:00"}) + "\n")
        sink.write('{"event": "applied", "job_id": "1", "ti')          # still being written
    assert [e["event"] for e in run.new_events()] == ["run_started"]
    assert run.new_events() == []
    with open(run.events_path, "a", encoding="utf-8") as sink:
        sink.write('tle": "Dev"}\nnot json\n{"event": "made_up"}\n{"event": "failed"}\n')
    (applied,) = run.new_events()                       # junk, unknown, and id-less lines dropped
    assert applied == {"event": "applied", "job_id": "1", "title": "Dev"}


STAND_IN_ENGINE = '''
import json, os, sys, time
sys.path.insert(0, os.getcwd())          # runAiBot.py sits in the project root; this script doesn't
from modules import run_hooks
config = json.load(open(os.environ["APPLYXAI_RUN_CONFIG"], encoding="utf-8"))
run_hooks.emit("run_started", search_terms=config["search"]["search_terms"])
stopped = False
try:
    for n in range(1, 400):
        run_hooks.checkpoint(sleep=lambda s: time.sleep(0.05))
        run_hooks.emit("job_started", job_id=str(n), title="Job %d" % n, company="Acme")
        run_hooks.emit("skipped", job_id=str(n), reason="stand-in")
        time.sleep(0.05)
except run_hooks.StopRequested:
    stopped = True
run_hooks.emit("run_finished", stopped=stopped, error="")
'''


def test_a_real_subprocess_follows_pause_and_stop(tmp_path, monkeypatch):
    '''Real process, real environment, real control file; only runAiBot.py is replaced.'''
    import time
    import automation.runner as runner_module
    script = tmp_path / "engine.py"
    script.write_text(STAND_IN_ENGINE, encoding="utf-8")
    monkeypatch.setattr(runner_module, "ENGINE_SCRIPT", script)
    run = EngineRun(Workspace(tmp_path / "ws"), "live")
    run.start({"search": {"search_terms": ["Dev"]}})

    def wait_for(predicate, seconds=20):
        deadline, seen = time.monotonic() + seconds, []
        while time.monotonic() < deadline:
            seen += run.new_events()
            if predicate(seen):
                return seen
            time.sleep(0.05)
        raise AssertionError(f"timed out; events so far: {[e['event'] for e in seen]}")

    events = wait_for(lambda seen: sum(e["event"] == "skipped" for e in seen) >= 2)
    run.pause()
    events += wait_for(lambda seen: any(e["event"] == "paused" for e in seen))
    time.sleep(0.4)
    assert not [e for e in run.new_events() if e["event"] == "job_started"]      # idle while paused
    run.resume()
    events += wait_for(lambda seen: any(e["event"] == "resumed" for e in seen))
    assert run.stop(timeout=20) == 0
    events += run.new_events()

    kinds = [e["event"] for e in events]
    assert kinds[0] == "run_started" and events[0]["search_terms"] == ["Dev"]
    assert kinds[-1] == "run_finished" and events[-1]["stopped"] is True
    assert not run.running


def test_parse_time_assumes_local_time_only_without_an_offset():
    aware = ev.parse_time("2026-10-07T05:30:00+05:30")
    assert aware.isoformat() == "2026-10-07T00:00:00+00:00"
    assert ev.parse_time("2026-10-07 10:00:00.5").tzinfo is not None
    assert ev.parse_time("Pending") is None and ev.parse_time(None) is None
