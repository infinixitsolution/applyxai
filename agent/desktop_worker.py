"""
Headless automation worker for ApplyXAI Desktop.
Runs the local wake listener and the run supervisor when this computer is connected.
"""

from __future__ import annotations

import logging
import sys
import threading
import time

from agent.engine_bootstrap import run_engine_child_if_requested

if run_engine_child_if_requested():
    raise SystemExit(0)

from agent import AGENT_VERSION, config
from agent.client import ApiClient
from agent.local_wake import start_wake_server
from agent.supervisor import AgentStopped, Supervisor

logger = logging.getLogger("applyxai.agent.worker")

_supervisor_lock = threading.Lock()
_supervisor_thread: threading.Thread | None = None
_active_supervisor: Supervisor | None = None
_pending_nudge = False


def _supervisor_running() -> bool:
    return _supervisor_thread is not None and _supervisor_thread.is_alive()


def _run_supervisor() -> None:
    global _active_supervisor, _pending_nudge
    cfg = config.load(config.default_home())
    if cfg is None:
        logger.info("This computer is not connected yet.")
        return
    supervisor: Supervisor | None = None
    try:
        client = ApiClient(cfg.server, cfg.token, verify_ssl=cfg.server.startswith("https://"))
        supervisor = Supervisor(client, config.default_home(), cfg.user_id)
        with _supervisor_lock:
            _active_supervisor = supervisor
            if _pending_nudge:
                supervisor.nudge()
                _pending_nudge = False
        logger.info("ApplyXAI worker %s connected to %s.", AGENT_VERSION, cfg.server)
        supervisor.run_forever()
    except AgentStopped as exc:
        logger.warning("%s", exc)
    except Exception:
        logger.exception("Supervisor stopped unexpectedly")
    finally:
        with _supervisor_lock:
            if _active_supervisor is supervisor:
                _active_supervisor = None


def start_supervisor_if_needed() -> None:
    global _supervisor_thread
    with _supervisor_lock:
        if _supervisor_running():
            return
        _supervisor_thread = threading.Thread(target=_run_supervisor, name="applyxai-supervisor", daemon=True)
        _supervisor_thread.start()


def on_local_wake() -> None:
    """Start the supervisor if needed, then interrupt idle sleep so a queued run is claimed now."""
    global _pending_nudge
    start_supervisor_if_needed()
    with _supervisor_lock:
        if _active_supervisor is not None:
            _active_supervisor.nudge()
        else:
            _pending_nudge = True


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--live-capture", "--live-capture-probe"):
        from agent.live_capture_stdio import main as live_capture_main

        return live_capture_main(sys.argv[1:])

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    wake = start_wake_server(on_local_wake)
    if wake is None:
        logger.info("Another ApplyXAI worker is already running on port 39217; exiting.")
        return 0
    start_supervisor_if_needed()
    logger.info("ApplyXAI agent worker v%s running (wake port %s).", AGENT_VERSION, 39217)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Worker stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
