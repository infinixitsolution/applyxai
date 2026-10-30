"""Check for Google Chrome updates on Windows before automation starts."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from modules.helpers import chrome_profile_launch_args, logger, print_lg

_VERSION_RE = re.compile(r"(\d+)\.\d+\.\d+\.\d+")


def find_chrome_executable() -> Path | None:
    roots = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    for root in roots:
        if not root:
            continue
        candidate = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if candidate.is_file():
            return candidate
    return None


def read_chrome_version(chrome: Path | None = None) -> str | None:
    exe = chrome or find_chrome_executable()
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        match = _VERSION_RE.search(text)
        return match.group(0) if match else text or None
    except Exception as exc:
        logger.warning("Could not read Chrome version: %s", exc)
        return None


def read_chrome_major_version(chrome: Path | None = None) -> int | None:
    version = read_chrome_version(chrome)
    if not version:
        return None
    match = _VERSION_RE.search(version)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _google_update_commands() -> list[list[str]]:
    if os.name != "nt":
        return []
    commands: list[list[str]] = []
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    legacy = Path(pf86) / "Google" / "Update" / "GoogleUpdate.exe"
    if legacy.is_file():
        commands.append([str(legacy), "/ua", "/installsource", "scheduler"])
    updater_root = Path(pf86) / "Google" / "GoogleUpdater"
    if updater_root.is_dir():
        for updater in sorted(updater_root.glob("**/updater.exe")):
            commands.append([str(updater), "--update", "--app-id", "com.google.Chrome"])
            break
    return commands


def _run_update_commands(timeout_sec: float = 180) -> None:
    for cmd in _google_update_commands():
        try:
            print_lg(f"Checking for Google Chrome updates ({Path(cmd[0]).name})…")
            subprocess.run(
                cmd,
                timeout=timeout_sec,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            print_lg("Chrome update is still running in the background…")
        except Exception as exc:
            logger.debug("Chrome update command failed: %s", exc)


def _nudge_profile_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", os.environ.get("TEMP", "."))) / "ApplyXAI" / "chrome-update-nudge"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _nudge_chrome_startup(chrome: Path) -> None:
    """Brief headless Chrome launch encourages Google Update to finish pending installs."""
    try:
        profile_flags = chrome_profile_launch_args(str(_nudge_profile_dir()))
        proc = subprocess.Popen(
            [
                str(chrome),
                *profile_flags,
                "--headless=new",
                "--disable-gpu",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        time.sleep(8)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as exc:
        logger.debug("Chrome startup nudge failed: %s", exc)


def looks_like_chrome_version_problem(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    needles = (
        "only supports chrome version",
        "version mismatch",
        "chrome version",
        "session not created",
        "this version of chromedriver",
        "needs to be updated",
        "google chrome",
    )
    return any(n in text for n in needles)


def prepare_chrome_for_run(*, wait_timeout_sec: int = 420) -> None:
    """On Windows, trigger Chrome update and wait until the installed version changes or time runs out."""
    if os.name != "nt":
        return
    chrome = find_chrome_executable()
    if not chrome:
        return
    before = read_chrome_version(chrome)
    print_lg(f"Google Chrome {before or 'unknown version'} — checking for updates before automation…")
    _run_update_commands(timeout_sec=min(180, wait_timeout_sec))
    deadline = time.time() + wait_timeout_sec
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        if attempt == 1:
            _nudge_chrome_startup(chrome)
        _run_update_commands(timeout_sec=90)
        after = read_chrome_version(chrome)
        if after and after != before:
            print_lg(f"Google Chrome updated to {after}. Starting automation…")
            return
        if attempt == 1:
            print_lg("Waiting for Google Chrome to finish updating (you can watch the taskbar if Chrome opens)…")
        time.sleep(15)
    print_lg(f"Proceeding with Google Chrome {read_chrome_version(chrome) or before or 'unknown'}.")


def refresh_chrome_and_retry_message() -> None:
    print_lg("Chrome and ChromeDriver did not match. Running Google Update, then retrying…")
    prepare_chrome_for_run(wait_timeout_sec=300)
