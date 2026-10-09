"""One-click connect: open browser, user approves while logged in, agent polls for token."""

from __future__ import annotations

import time
import webbrowser
from pathlib import Path
from typing import Callable

from agent import AGENT_VERSION
from agent.client import ApiClient, ApiError, NetworkError
from agent.config import AgentConfig, check_server_url, default_device_name, platform_name, save

LogFn = Callable[[str], None]

POLL_SECONDS = 2.0
MAX_WAIT_SECONDS = 15 * 60


def connect_with_browser(
    *,
    api_base: str,
    web_base: str,
    home: Path,
    log: LogFn | None = None,
) -> AgentConfig:
    """Start connect session, open browser, poll until approved."""

    def _log(msg: str) -> None:
        if log:
            log(msg)

    server = check_server_url(api_base, allow_insecure=True)
    web = check_server_url(web_base, allow_insecure=True)
    client = ApiClient(server, verify_ssl=server.startswith("https://"))
    _log(f"Starting secure connect to {server}...")
    started = client.connect_start(name=default_device_name(), platform=platform_name(), agent_version=AGENT_VERSION)
    session_id = started["session_id"]
    secret = started["secret"]
    url = f"{web}/app/automation/connect?session={session_id}"
    _log("Opening your browser — sign in if needed, then approve this computer.")
    webbrowser.open(url)
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            poll = client.connect_poll(session_id, secret)
        except NetworkError as exc:
            _log(str(exc))
            time.sleep(POLL_SECONDS)
            continue
        if poll.get("status") == "ready":
            cfg = AgentConfig(
                server=server,
                token=poll["token"],
                device_id=poll["device_id"],
                user_id=poll["user_id"],
                name=poll.get("name") or default_device_name(),
            )
            save(home, cfg)
            _log(f"Connected as {cfg.name}")
            return cfg
        time.sleep(POLL_SECONDS)
    raise TimeoutError("Timed out waiting for approval in the browser.")
