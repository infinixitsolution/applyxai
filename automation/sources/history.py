"""Per-site applied and failed CSV paths.

LinkedIn and Naukri both use numeric job ids, so each site keeps its own files.
LinkedIn also still reads the legacy history/applied.csv from before the split.
"""

from __future__ import annotations

import csv
from pathlib import Path


def paths_for(applied_csv: str, platform: str) -> tuple[str, str]:
    """Return (applied.csv, failed.csv) under the history directory for this site."""
    base = Path(applied_csv).resolve()
    folder = base.parent / platform
    folder.mkdir(parents=True, exist_ok=True)
    return (folder / "applied.csv").as_posix(), (folder / "failed.csv").as_posix()


def read_job_ids(*paths: str) -> set[str]:
    found: set[str] = set()
    for path in paths:
        if not path:
            continue
        try:
            with open(path, "r", encoding="utf-8", newline="") as handle:
                for row in csv.reader(handle):
                    if row and row[0] and row[0] != "Job ID":
                        found.add(row[0].strip())
        except FileNotFoundError:
            continue
    return found
