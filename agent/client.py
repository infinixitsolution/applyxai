"""HTTP client for the /api/agent endpoints. Unwraps the {success, data | error} envelope."""

import requests

from agent import AGENT_VERSION
from agent.config import platform_name

TIMEOUT = 30


class ApiError(Exception):
    """The server answered with an error envelope."""

    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


class NetworkError(Exception):
    """The server couldn't be reached, or didn't answer with JSON. Safe to retry."""


class ApiClient:
    def __init__(self, server: str, token: str = "", *, session=None, timeout: float = TIMEOUT, verify_ssl: bool = True):
        self.server = server.rstrip("/")
        self._token = token
        self._session = session or requests.Session()
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        if not verify_ssl:
            # Disable SSL warnings for self-signed certificates
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def __repr__(self) -> str:
        return f"ApiClient(server={self.server!r})"

    def _send(self, method: str, path: str, *, json=None, raw: bool = False):
        headers = {"User-Agent": f"ApplyXAI-Agent/{AGENT_VERSION}"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = self._session.request(method, f"{self.server}/api{path}", json=json, headers=headers,
                                         timeout=self._timeout, verify=self._verify_ssl)
        except (requests.RequestException, OSError) as exc:
            raise NetworkError(f"Couldn't reach {self.server}: {type(exc).__name__}") from None
        if raw and resp.status_code == 200:
            return resp.content
        try:
            body = resp.json()
        except ValueError:
            raise NetworkError(f"Unexpected response from the server (HTTP {resp.status_code}).") from None
        if resp.status_code >= 500:
            raise NetworkError(f"The server had a problem (HTTP {resp.status_code}).")
        if not isinstance(body, dict) or not body.get("success"):
            error = body.get("error") if isinstance(body, dict) else None
            error = error if isinstance(error, dict) else {}
            raise ApiError(resp.status_code, error.get("code", "HTTP_ERROR"),
                           error.get("message", f"HTTP {resp.status_code}"), error.get("details"))
        return body.get("data") or {}

    def pair(self, code: str, name: str) -> dict:
        return self._send("POST", "/agent/pair", json={
            "code": code, "name": name, "platform": platform_name(), "agent_version": AGENT_VERSION})

    def me(self) -> dict:
        return self._send("GET", "/agent/me")

    def unpair(self) -> dict:
        return self._send("POST", "/agent/unpair")

    def poll(self, active_run_id: str | None = None) -> dict:
        return self._send("POST", "/agent/poll", json={
            "active_run_id": active_run_id, "platform": platform_name(), "agent_version": AGENT_VERSION})

    def download_resume(self, run_id: str) -> bytes:
        return self._send("GET", f"/agent/runs/{run_id}/resume", raw=True)

    def post_events(self, run_id: str, first_seq: int, events: list[dict]) -> dict:
        return self._send("POST", f"/agent/runs/{run_id}/events", json={"first_seq": first_seq, "events": events})
