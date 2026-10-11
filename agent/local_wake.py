"""Local HTTP listener so the web app can nudge this GUI to start the agent (127.0.0.1 only)."""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable

logger = logging.getLogger("applyxai.agent.wake")

DEFAULT_PORT = 39217


def start_wake_server(on_wake: Callable[[], None], port: int = DEFAULT_PORT) -> HTTPServer | None:
    """Bind localhost; returns None if the port is already in use (another agent instance)."""

    class WakeHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            logger.debug("wake %s - %s", self.address_string(), format % args)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] in ("/wake", "/start"):
                try:
                    on_wake()
                except Exception:
                    logger.exception("wake callback failed")
                self.send_response(204)
            else:
                self.send_response(404)
            self.end_headers()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.end_headers()

    try:
        server = HTTPServer(("127.0.0.1", port), WakeHandler)
    except OSError as exc:
        logger.info("Local wake server not started on %s (%s)", port, exc)
        return None
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="applyxai-wake")
    thread.start()
    logger.info("Local wake server listening on http://127.0.0.1:%s/wake", port)
    return server
