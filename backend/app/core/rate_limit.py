"""Moving-window rate limits backed by `limits` (in-memory for dev, Redis in production)."""

import math
import time
from functools import lru_cache

from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter

from backend.app.core.config import settings
from backend.app.core.errors import AppError


class RateLimiter:
    def __init__(self, storage_url: str):
        self._storage = storage_from_string(storage_url)
        self._limiter = MovingWindowRateLimiter(self._storage)

    def hit(self, rule: str, *identifiers: str) -> None:
        """Count one attempt against `rule` (e.g. "5/minute"); raise RATE_LIMITED when exceeded."""
        item = parse(rule)
        if self._limiter.hit(item, *identifiers):
            return
        reset_at, _remaining = self._limiter.get_window_stats(item, *identifiers)
        retry_after = max(1, math.ceil(reset_at - time.time()))
        raise AppError("RATE_LIMITED", "Too many attempts. Please wait and try again.", 429,
                       headers={"Retry-After": str(retry_after)})

    def reset(self) -> None:
        self._storage.reset()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(settings.RATE_LIMIT_STORAGE_URL)
