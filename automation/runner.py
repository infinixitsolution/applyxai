"""
Runs the existing engine (runAiBot.py) as a supervised subprocess.

Per-user workspace layout:

    <workspace>/profile/                Chrome profile; keeps the LinkedIn login between runs
    <workspace>/history/applied.csv     the engine's own CSVs, kept across runs so it never
    <workspace>/history/failed.csv      re-applies to a job it already handled
    <workspace>/runs/<run_id>/config.json, events.jsonl, control, engine.log, logs/

Pause and stop go through the control file, which the engine reads between jobs, so a job
in progress is never cut off halfway. `stop()` falls back to killing the process tree when
the engine doesn't exit in time (for example while it waits for a LinkedIn sign-in).
"""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from automation import events as ev
from modules.run_hooks import CONTROL_ENV, EVENTS_ENV, MAX_APPLIED_ENV, PROFILE_ENV

ENGINE_ROOT = Path(__file__).resolve().parent.parent
ENGINE_SCRIPT = ENGINE_ROOT / "runAiBot.py"
RUN_CONFIG_ENV = "APPLYXAI_RUN_CONFIG"

RUNNING, PAUSE, STOP = "run", "pause", "stop"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RunnerError(RuntimeError):
    pass


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.profile_dir = self.root / "profile"
        self.history_dir = self.root / "history"

    def run_dir(self, run_id: str) -> Path:
        if not _SAFE_ID.match(run_id):
            raise RunnerError("invalid run id")
        return self.root / "runs" / run_id


class EngineRun:
    def __init__(self, workspace: Workspace, run_id: str, *, python: str = sys.executable,
                 popen=subprocess.Popen):
        self.workspace = workspace
        self.run_id = run_id
        self.dir = workspace.run_dir(run_id)
        self.config_path = self.dir / "config.json"
        self.events_path = self.dir / "events.jsonl"
        self.control_path = self.dir / "control"
        self.log_path = self.dir / "engine.log"
        self._python = python
        self._popen = popen
        self._proc = None
        self._offset = 0

    # ---------------------------------------------------------------- lifecycle
    def start(self, config: dict, *, max_applied: int | None = None) -> None:
        """Launch the engine. With `max_applied`, it stops by itself after that many applications."""
        if self._proc is not None:
            raise RunnerError("this run has already been started")
        for path in (self.dir, self.workspace.profile_dir, self.workspace.history_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_control(RUNNING)
        self.events_path.touch()

        env = os.environ.copy()
        env.update({
            RUN_CONFIG_ENV: str(self.config_path),
            EVENTS_ENV: str(self.events_path),
            CONTROL_ENV: str(self.control_path),
            PROFILE_ENV: str(self.workspace.profile_dir),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        env.pop(MAX_APPLIED_ENV, None)
        if max_applied is not None:
            env[MAX_APPLIED_ENV] = str(max(int(max_applied), 0))
        kwargs = {"cwd": str(ENGINE_ROOT), "env": env, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        with open(self.log_path, "w", encoding="utf-8") as log:
            self._proc = self._popen([self._python, str(ENGINE_SCRIPT)], stdout=log, **kwargs)

    def pause(self) -> None:
        self._write_control(PAUSE)

    def resume(self) -> None:
        self._write_control(RUNNING)

    def request_stop(self) -> None:
        """Ask the engine to stop after the current job, without waiting for it."""
        self._write_control(STOP)

    def stop(self, timeout: float = 60) -> int | None:
        """Ask the engine to stop after the current job; kill it if it hasn't exited by `timeout`."""
        self.request_stop()
        if self._proc is None:
            return None
        try:
            return self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            return self._proc.poll()

    def kill(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ---------------------------------------------------------------- status
    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def returncode(self) -> int | None:
        return None if self._proc is None else self._proc.poll()

    def control_state(self) -> str:
        try:
            return self.control_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def new_events(self) -> list[dict]:
        events, self._offset = ev.read_events(str(self.events_path), self._offset)
        return events

    def _write_control(self, state: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.control_path.with_suffix(".tmp")
        tmp.write_text(state, encoding="utf-8")
        os.replace(tmp, self.control_path)
