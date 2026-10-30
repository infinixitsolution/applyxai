"""One automation Chrome session per PC (avoids duplicate browsers and chromedriver locks)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_LOCK: "_EngineLock | None" = None


class _EngineLock:
    def __init__(self) -> None:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE") or "."
        self._path = Path(base) / "ApplyXAI" / "agent" / "engine-session.lock"
        self._file = None

    def acquire(self) -> bool:
        if self._file is not None:
            return True
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a+b")
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                self._file.close()
                self._file = None
                return False
        else:
            import fcntl

            try:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self._file.close()
                self._file = None
                return False
        self._file.seek(0)
        self._file.truncate()
        self._file.write(str(os.getpid()).encode("ascii"))
        self._file.flush()
        return True

    def release(self) -> None:
        if self._file is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._file.close()
        except OSError:
            pass
        self._file = None


def engine_lock() -> _EngineLock:
    global _LOCK
    if _LOCK is None:
        _LOCK = _EngineLock()
    return _LOCK
