"""Where the agent keeps its device token and workspace."""

import json
import os
import platform
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

HOME_ENV = "APPLYXAI_AGENT_HOME"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def default_home() -> Path:
    if os.environ.get(HOME_ENV):
        return Path(os.environ[HOME_ENV])
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "ApplyXAI" / "agent"
    return Path.home() / ".applyxai" / "agent"


def platform_name() -> str:
    return f"{platform.system()} {platform.release()}".strip()[:50]


def default_device_name() -> str:
    return (socket.gethostname() or "My computer")[:100]


def check_server_url(url: str, *, allow_insecure: bool = False) -> str:
    """The server URL without a trailing slash. Plain http is only allowed for this computer."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("The server address must start with https:// (for example https://app.applyxai.com).")
    if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS and not allow_insecure:
        raise ValueError("Use an https:// address so your device token can't be read on the network.")
    return url.strip().rstrip("/")


@dataclass
class AgentConfig:
    server: str
    token: str
    device_id: str
    user_id: str
    name: str = ""

    def __repr__(self) -> str:                      # keep the token out of logs and tracebacks
        return f"AgentConfig(server={self.server!r}, device_id={self.device_id!r}, name={self.name!r})"


def config_path(home: Path) -> Path:
    return home / "agent.json"


def load(home: Path) -> AgentConfig | None:
    try:
        data = json.loads(config_path(home).read_text(encoding="utf-8"))
        return AgentConfig(**{k: data[k] for k in ("server", "token", "device_id", "user_id")}, name=data.get("name", ""))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save(home: Path, config: AgentConfig) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = config_path(home)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    if os.name != "nt":
        os.chmod(tmp, 0o600)                         # %LOCALAPPDATA% is already private to the user
    os.replace(tmp, path)
    return path


def forget(home: Path) -> None:
    try:
        config_path(home).unlink()
    except FileNotFoundError:
        pass
