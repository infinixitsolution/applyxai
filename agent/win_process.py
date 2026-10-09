"""Windows subprocess flags — hide console windows for background agent/engine."""

from __future__ import annotations

import os
import subprocess

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def background_creationflags(*, new_process_group: bool = False) -> int:
    """No visible console on Windows; optional new process group for taskkill trees."""
    if os.name != "nt":
        return 0
    flags = CREATE_NO_WINDOW
    if new_process_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return flags
