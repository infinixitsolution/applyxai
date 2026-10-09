"""
Runs the engine for runs claimed from the server, and reports what happens.

Every engine event gets a sequence number and stays in the outbox until the server confirms
it, so nothing is lost or counted twice when the connection drops. Each server reply says
whether the engine should run, pause, or stop. The plan limit is passed to the engine as
APPLYXAI_MAX_APPLIED, so it stops by itself at the cap; as a backstop, once the applications
not yet confirmed reach what the server says is left, the engine is told to stop without
waiting for the next reply.
"""

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.client import ApiClient, ApiError, NetworkError
from automation import events as ev
from automation.run_config import RunConfigError, build_run_config
from automation.runner import EngineRun, Workspace

logger = logging.getLogger("applyxai.agent")

IDLE_POLL_SECONDS = 5.0
MAX_IDLE_BACKOFF = 60.0
TICK_SECONDS = 1.0
HEARTBEAT_SECONDS = 5.0
STOP_GRACE_SECONDS = 90.0
FLUSH_DEADLINE_SECONDS = 600.0
MAX_BATCH = 200


class AgentStopped(Exception):
    """The server no longer accepts this computer (it was disconnected); pairing again is needed."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resume_filename(name: str, file_type: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9 ._-]", "", Path(name or "").stem).strip(" .")[:80] or "resume"
    return f"{stem}.{file_type}"


class Outbox:
    """Numbered events waiting for the server to confirm them."""

    def __init__(self, next_seq: int = 1):
        self.next_seq = next_seq
        self.pending: list[tuple[int, dict]] = []

    def add(self, event: dict) -> None:
        self.pending.append((self.next_seq, event))
        self.next_seq += 1

    def batch(self) -> tuple[int, list[dict]]:
        first = self.pending[0][0] if self.pending else self.next_seq
        return first, [e for _, e in self.pending[:MAX_BATCH]]

    def ack(self, server_next_seq: int) -> None:
        self.pending = [(s, e) for s, e in self.pending if s >= server_next_seq]

    def renumber_from(self, seq: int) -> None:
        self.pending = [(seq + i, e) for i, (_, e) in enumerate(self.pending)]
        self.next_seq = seq + len(self.pending)

    def count(self, kind: str) -> int:
        return sum(1 for _, e in self.pending if e.get("event") == kind)


class Supervisor:
    def __init__(self, client: ApiClient, home: Path, user_id: str, *, engine_factory=EngineRun,
                 sleep=time.sleep, clock=time.monotonic):
        self.client = client
        self.workspace = Workspace(Path(home) / "workspace" / user_id)
        self._engine_factory = engine_factory
        self._sleep = sleep
        self._clock = clock

    # ------------------------------------------------------------------ idle loop
    def run_forever(self) -> None:
        delay = IDLE_POLL_SECONDS
        while True:
            try:
                self.run_once()
                delay = IDLE_POLL_SECONDS
            except NetworkError as exc:
                logger.warning("%s Retrying in %d seconds.", exc, delay)
                delay = min(delay * 2, MAX_IDLE_BACKOFF)
            self._sleep(delay)

    def run_once(self) -> bool:
        """Poll once and carry out the run the server hands out, if any. True if a run was done."""
        try:
            data = self.client.poll()
        except ApiError as exc:
            if exc.status == 401:
                raise AgentStopped(exc.message) from None
            raise NetworkError(exc.message) from None
        if not data.get("run"):
            return False
        self.execute(data["run"])
        return True

    # ------------------------------------------------------------------ one run
    def execute(self, payload: dict) -> None:
        run = _RunSession(self, payload)
        try:
            run.go()
        except KeyboardInterrupt:
            logger.info("Stopping the run before exiting…")
            run.abort(stopped=True)
            raise


class _RunSession:
    def __init__(self, supervisor: Supervisor, payload: dict):
        self.s = supervisor
        self.client = supervisor.client
        self.run_id = payload["id"]
        self.payload = payload
        self.engine = supervisor._engine_factory(supervisor.workspace, self.run_id)
        self.outbox = Outbox(int(payload.get("next_seq") or 1))
        self.remaining = payload.get("remaining_applications")
        self.control = payload.get("control") or "run"
        self.applied_control = "run"
        self.stop_requested_at = None
        self.last_post = float("-inf")
        self.saw_finish = False
        self.counts = dict.fromkeys(sorted(ev.OUTCOMES), 0)

    def _finished_event(self, *, stopped: bool, error: str = "") -> dict:
        return {"event": ev.RUN_FINISHED, "ts": _now_iso(), **self.counts, "stopped": stopped, "error": error}

    # -- setup
    def _prepare(self) -> dict:
        resume = self.payload.get("resume")
        if not resume:
            raise RunConfigError(["Upload a resume and make it your default."])
        self.engine.dir.mkdir(parents=True, exist_ok=True)
        path = self.engine.dir / _resume_filename(resume.get("filename", ""), resume.get("file_type", "pdf"))
        path.write_bytes(self.client.download_resume(self.run_id))
        qa = self.payload.get("application_qa") or {}
        use_ai = bool(qa.get("ai_applications_enabled")) and bool(self.payload.get("ai_available"))
        applyxai_qa = {
            "human_questions": qa.get("human_questions") or [],
            "ai_policy": qa.get("ai_policy") or {},
            "ai_available": bool(self.payload.get("ai_available")),
            "run_id": self.run_id,
            "resume_mode": self.payload.get("resume_mode") or "default",
        }
        return build_run_config(
            self.payload.get("values") or {},
            history_dir=self.s.workspace.history_dir,
            run_dir=self.engine.dir,
            resume_path=path,
            dry_run=bool(self.payload.get("dry_run")),
            use_ai=use_ai,
            applyxai_qa=applyxai_qa,
        )

    def go(self) -> None:
        logger.info("Starting run %s%s.", self.run_id, " (dry run: nothing is submitted)" if self.payload.get("dry_run") else "")
        try:
            config = self._prepare()
        except (RunConfigError, ApiError, NetworkError, OSError) as exc:
            message = exc.message if isinstance(exc, ApiError) else str(exc)
            logger.error("The run couldn't start: %s", message)
            self.outbox.add(self._finished_event(stopped=False, error=f"The run couldn't start: {message}"))
            self._flush_all()
            return
        if self.control == "stop":
            self.outbox.add(self._finished_event(stopped=True))
            self._flush_all()
            return
        cap = None if self.remaining is None or self.payload.get("dry_run") else int(self.remaining)
        extra_env = {
            "APPLYXAI_API_BASE": self.s.client.server,
            "APPLYXAI_AGENT_TOKEN": self.s.client.token,
            "APPLYXAI_RUN_ID": self.run_id,
        }
        self.engine.start(config, max_applied=cap, extra_env=extra_env)
        self._apply_control()
        self._supervise()

    # -- main loop
    def _supervise(self) -> None:
        while True:
            self._collect()
            self._enforce_limit()
            if self.outbox.pending or self.s._clock() - self.last_post >= HEARTBEAT_SECONDS:
                self._post()
            if not self.engine.running:
                break
            if self.stop_requested_at is not None and self.s._clock() - self.stop_requested_at > STOP_GRACE_SECONDS:
                logger.warning("The engine didn't stop in time; closing it.")
                self.engine.kill()
            self.s._sleep(TICK_SECONDS)
        self._finish()

    def _collect(self) -> None:
        for event in self.engine.new_events():
            self.outbox.add(event)
            self._announce(event)

    def _announce(self, event: dict) -> None:
        kind = event.get("event")
        if kind == ev.RUN_FINISHED:
            self.saw_finish = True
        if kind in self.counts:
            self.counts[kind] += 1
        if kind == ev.LOGIN_REQUIRED:
            logger.warning("Sign in to LinkedIn in the browser window that just opened. The run continues after that.")
        elif kind == ev.APPLIED:
            logger.info("Applied: %s at %s", event.get("title", ""), event.get("company", ""))
        elif kind == ev.FAILED:
            logger.info("Couldn't apply to job %s: %s", event.get("job_id"), event.get("reason", ""))
        elif kind == ev.RUN_FINISHED:
            logger.info("Run finished: %s applied, %s failed, %s skipped.",
                        event.get("applied", 0), event.get("failed", 0), event.get("skipped", 0))

    def _enforce_limit(self) -> None:
        if self.remaining is not None and self.outbox.count(ev.APPLIED) >= self.remaining and self.control != "stop":
            logger.info("This month's application limit is reached; stopping after the current job.")
            self.control = "stop"
            self._apply_control()

    def _apply_control(self) -> None:
        if self.applied_control == "stop" or self.control == self.applied_control:
            return
        if self.control == "stop":
            self.engine.request_stop()
            self.stop_requested_at = self.s._clock()
        elif self.control == "pause":
            self.engine.pause()
            logger.info("Pausing after the current job.")
        else:
            self.engine.resume()
            logger.info("Resuming.")
        self.applied_control = self.control

    def _post(self) -> bool:
        first, events = self.outbox.batch()
        try:
            data = self.client.post_events(self.run_id, first, events)
        except NetworkError as exc:
            logger.warning("%s Results are kept and will be sent when the connection is back.", exc)
            self.last_post = self.s._clock()
            return False
        except ApiError as exc:
            if exc.code == "SEQUENCE_GAP" and isinstance(exc.details, dict) and "next_seq" in exc.details:
                self.outbox.renumber_from(int(exc.details["next_seq"]))
                return False
            if exc.status in (401, 404):
                logger.error("%s Stopping the run.", exc.message)
                self.engine.request_stop()
                self.engine.kill()
                raise AgentStopped(exc.message) from None
            logger.warning("The server refused the update: %s", exc.message)
            self.last_post = self.s._clock()
            return False
        self.last_post = self.s._clock()
        self.outbox.ack(int(data.get("next_seq", first + len(events))))
        self.remaining = data.get("remaining_applications", self.remaining)
        server_control = data.get("control") or "run"
        if self.control != "stop":
            self.control = server_control
            self._apply_control()
        return True

    # -- shutdown
    def _finish(self) -> None:
        self._collect()
        if not self.saw_finish:
            stopped = self.stop_requested_at is not None
            code = self.engine.returncode
            error = "" if stopped else (f"The automation engine closed unexpectedly (exit code {code}). "
                                        f"Details are in {self.engine.log_path} on your computer.")
            self.outbox.add(self._finished_event(stopped=stopped, error=error))
        self._flush_all()

    def _flush_all(self, deadline_seconds: float = FLUSH_DEADLINE_SECONDS) -> None:
        deadline = self.s._clock() + deadline_seconds
        while self.outbox.pending:
            if self._post():
                continue
            if self.s._clock() >= deadline:
                logger.error("Couldn't send the last %d updates to the server. The run's files are in %s.",
                             len(self.outbox.pending), self.engine.dir)
                return
            self.s._sleep(HEARTBEAT_SECONDS)

    def abort(self, *, stopped: bool) -> None:
        """Ctrl+C: stop the engine politely, then send what's left (briefly)."""
        if self.engine.running:
            self.engine.stop(timeout=STOP_GRACE_SECONDS)
        self.stop_requested_at = self.stop_requested_at or self.s._clock()
        self._collect()
        if not self.saw_finish:
            self.outbox.add(self._finished_event(stopped=stopped))
        self._flush_all(deadline_seconds=30)
