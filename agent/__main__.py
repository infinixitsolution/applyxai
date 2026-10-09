"""
ApplyXAI desktop agent. From the project folder, with the virtual environment active:

    python -m agent connect --preset live                    # one-click (opens browser)
    python -m agent pair --server https://app.example.com   # legacy pairing code
    python -m agent run                                      # keep this window open while runs go
    python -m agent status
    python -m agent unpair
"""

import argparse
import logging
import sys
from pathlib import Path

from agent.engine_bootstrap import run_engine_child_if_requested

if run_engine_child_if_requested():
    raise SystemExit(0)

from agent import AGENT_VERSION, config
from agent.client import ApiClient, ApiError, NetworkError
from agent.supervisor import AgentStopped, Supervisor


def _home(args) -> Path:
    return Path(args.home) if args.home else config.default_home()


def _connect(args) -> int:
    home = _home(args)
    try:
        p = config.preset(args.preset)
    except ValueError as exc:
        print(exc)
        return 2
    try:
        from agent.connect_flow import connect_with_browser

        cfg = connect_with_browser(
            api_base=p["api"],
            web_base=p["web"],
            home=home,
            log=print,
        )
    except (ApiError, NetworkError, TimeoutError, ValueError) as exc:
        print(getattr(exc, "message", None) or exc)
        return 1
    print(f"Connected to {cfg.server} as \"{cfg.name}\". Start the agent with: python -m agent run")
    return 0


def _pair(args) -> int:
    home = _home(args)
    try:
        server = config.check_server_url(args.server, allow_insecure=args.insecure)
    except ValueError as exc:
        print(exc)
        return 2
    code = args.code or input("Pairing code from the Automation page: ").strip()
    try:
        data = ApiClient(server, verify_ssl=False).pair(code, args.name or config.default_device_name())
    except (ApiError, NetworkError) as exc:
        print(getattr(exc, "message", None) or exc)
        return 1
    config.save(home, config.AgentConfig(server=server, token=data["token"], device_id=data["device_id"],
                                         user_id=data["user_id"], name=data.get("name", "")))
    print(f"Connected as \"{data.get('name', '')}\". Start the agent with: python -m agent run")
    return 0


def _load(args) -> config.AgentConfig | None:
    cfg = config.load(_home(args))
    if cfg is None:
        print("This computer isn't connected yet. Run: python -m agent connect --preset live")
    return cfg


def _run(args) -> int:
    cfg = _load(args)
    if cfg is None:
        return 2
    # Disable SSL verification for self-signed certificates in development
    supervisor = Supervisor(ApiClient(cfg.server, cfg.token, verify_ssl=False), _home(args), cfg.user_id)
    logging.getLogger("applyxai.agent").info(
        "ApplyXAI agent %s connected to %s. Waiting for runs; press Ctrl+C to quit.", AGENT_VERSION, cfg.server)
    try:
        supervisor.run_forever()
    except AgentStopped as exc:
        print(f"{exc}\nConnect this computer again with: python -m agent pair --server {cfg.server}")
        return 1
    except KeyboardInterrupt:
        print("Agent stopped.")
    return 0


def _status(args) -> int:
    cfg = _load(args)
    if cfg is None:
        return 2
    if args.check:
        try:
            ApiClient(cfg.server, cfg.token).me()
        except ApiError as exc:
            print(exc.message)
            return 1
        except NetworkError as exc:
            print(exc)
            return 1
    print(f"Connected to {cfg.server} as \"{cfg.name}\" (agent {AGENT_VERSION}). Files: {_home(args)}")
    return 0


def _unpair(args) -> int:
    home = _home(args)
    cfg = config.load(home)
    if cfg is not None:
        try:
            ApiClient(cfg.server, cfg.token).unpair()
        except (ApiError, NetworkError) as exc:
            print(f"Couldn't tell the server ({getattr(exc, 'message', None) or exc}); "
                  "remove this computer on the Automation page too.")
    config.forget(home)
    print("This computer is disconnected from ApplyXAI.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent", description="ApplyXAI desktop agent")
    parser.add_argument("--home", help=f"where the agent keeps its files (default: {config.default_home()})")
    sub = parser.add_subparsers(dest="command", required=True)

    connect = sub.add_parser("connect", help="one-click connect (opens browser; no pairing code)")
    connect.add_argument("--preset", choices=tuple(config.SERVER_PRESETS), default="live",
                         help="local = http://localhost:5173, live = https://applyxai.com")
    connect.set_defaults(func=_connect)

    pair = sub.add_parser("pair", help="legacy connect with a pairing code from the web app")
    pair.add_argument("--server", required=True, help="your ApplyXAI address, e.g. https://app.applyxai.com")
    pair.add_argument("--code", help="pairing code (asked for if omitted)")
    pair.add_argument("--name", help="name shown on the Automation page (default: this computer's name)")
    pair.add_argument("--insecure", action="store_true", help="allow a plain http:// address on your network")
    pair.set_defaults(func=_pair)

    sub.add_parser("run", help="wait for runs and carry them out").set_defaults(func=_run)
    status = sub.add_parser("status", help="show the connection")
    status.add_argument("--check", action="store_true", help="also check the server accepts this computer")
    status.set_defaults(func=_status)
    sub.add_parser("unpair", help="disconnect this computer").set_defaults(func=_unpair)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
