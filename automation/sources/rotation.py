"""Switch job sources after N successful submissions.

Skips and failures do not count. A blocked or exhausted source is left out, and the
run continues on another selected source when one is still available.
"""

from __future__ import annotations


def _label_ready(sources: list[str]) -> list[str]:
    ordered: list[str] = []
    for name in sources:
        if name in ("linkedin", "naukri") and name not in ordered:
            ordered.append(name)
    return ordered or ["linkedin"]


class Rotation:
    def __init__(self, sources: list[str], switch_after: int | None):
        self.sources = _label_ready(list(sources or []))
        self.switch_after = int(switch_after) if len(self.sources) > 1 and switch_after else None
        self.index = 0
        self.submitted_on_source = 0
        self.blocked: set[str] = set()
        self.exhausted: set[str] = set()
        self.cursors = {name: {"term_index": 0, "page": 1, "seen": []} for name in self.sources}
        self._announced: set[str] = set()
        self._last_switch_count = 0

    def current(self) -> str | None:
        if not self.sources:
            return None
        for _ in range(len(self.sources)):
            name = self.sources[self.index]
            if name not in self.blocked and name not in self.exhausted:
                return name
            self.index = (self.index + 1) % len(self.sources)
        return None

    def cursor(self, source: str) -> dict:
        return self.cursors[source]

    def budget(self) -> int | None:
        """How many more successful applications to take on the current source before switching."""
        if self.switch_after is None or not self._others_alive():
            return None
        return max(self.switch_after - self.submitted_on_source, 0)

    def begin_slice(self) -> dict | None:
        """Announce the first source. Later sources are announced by record/absorb."""
        source = self.current()
        if source is None or source in self._announced:
            return None
        if self._announced:
            return None
        self._announced.add(source)
        return {"event": "source_started", "source": source}

    def record(self, outcome: str, *, reason: str = "") -> list[dict]:
        """One job result: submitted, skipped, failed, exhausted, or blocked."""
        if outcome == "submitted":
            self.submitted_on_source += 1
            if self._should_switch():
                return self._switch()
            return []
        if outcome in ("skipped", "failed"):
            return []
        if outcome == "exhausted":
            return self.absorb("exhausted", 0, reason=reason)
        if outcome == "blocked":
            return self.absorb("blocked", 0, reason=reason)
        return []

    def absorb(self, status: str, submitted: int, *, reason: str = "") -> list[dict]:
        """Apply a batch from one source. `submitted` is successful on-site applications in that batch."""
        self.submitted_on_source += max(int(submitted), 0)
        if status == "limit":
            if self._others_alive():
                return self._switch()
            return []
        if status == "exhausted":
            current = self.sources[self.index]
            self.exhausted.add(current)
            return self._leave(current)
        if status == "blocked":
            current = self.sources[self.index]
            self.blocked.add(current)
            events = [{
                "event": "source_blocked",
                "source": current,
                "reason": reason or "This source cannot continue.",
            }]
            events.extend(self._leave(current))
            return events
        if self._should_switch():
            return self._switch()
        return []

    def _others_alive(self) -> bool:
        current = self.sources[self.index]
        return any(
            name != current and name not in self.blocked and name not in self.exhausted
            for name in self.sources
        )

    def _should_switch(self) -> bool:
        return bool(
            self.switch_after
            and self._others_alive()
            and self.submitted_on_source >= self.switch_after
        )

    def _switch(self) -> list[dict]:
        self._last_switch_count = self.submitted_on_source
        previous = self._last_switch_count
        self.submitted_on_source = 0
        self._advance()
        nxt = self.current()
        if nxt is None:
            return []
        self._announced.add(nxt)
        return [{"event": "source_switched", "source": nxt, "submitted_on_previous": previous}]

    def _leave(self, left: str) -> list[dict]:
        self._last_switch_count = self.submitted_on_source
        previous = self._last_switch_count
        self.submitted_on_source = 0
        self._advance()
        nxt = self.current()
        if nxt is None or nxt == left:
            return []
        self._announced.add(nxt)
        return [{"event": "source_switched", "source": nxt, "submitted_on_previous": previous}]

    def _advance(self) -> None:
        if not self.sources:
            return
        self.index = (self.index + 1) % len(self.sources)
        self.current()
