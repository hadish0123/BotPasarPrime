from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.security.security_contract import RateLimitExceeded


class RateLimiter:
    def __init__(self, limit: int = 60, window_seconds: int = 60):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Invalid rate limit configuration")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            events = self._events[key]

            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= self.limit:
                raise RateLimitExceeded("Rate limit exceeded")

            events.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


class LoginAttemptLimiter:
    def __init__(self, limit: int = 5, window_seconds: int = 900):
        self._limiter = RateLimiter(limit, window_seconds)

    def check(self, identity: str) -> None:
        self._limiter.check(f"login:{identity}")

    def reset(self, identity: str) -> None:
        self._limiter.reset(f"login:{identity}")
