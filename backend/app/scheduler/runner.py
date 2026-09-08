from __future__ import annotations

import threading
from collections.abc import Callable


class IdempotentScheduler:
    """
    Process-level scheduler guard.

    Persistent uniqueness is enforced by the database migration.
    The in-process lock prevents duplicate work from concurrent workers
    before the persistent claim is reached.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: set[str] = set()

    def run_once(
        self,
        run_key: str,
        claim: Callable[[str], bool],
        job: Callable[[], None],
    ) -> bool:
        with self._lock:
            if run_key in self._running:
                return False
            self._running.add(run_key)

        try:
            if not claim(run_key):
                return False

            job()
            return True
        finally:
            with self._lock:
                self._running.discard(run_key)
