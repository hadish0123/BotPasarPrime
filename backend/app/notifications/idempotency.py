from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class DeliveryRecord:
    event_key: str
    recipient_id: int
    delivered_at: datetime


class NotificationDeliveryLedger:
    """
    Process-level safety ledger.

    The database-backed notification ledger is added by the migration below.
    This class also protects concurrent scheduler workers inside one process.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._delivered: dict[str, DeliveryRecord] = {}

    def claim(self, event_key: str, recipient_id: int) -> bool:
        with self._lock:
            if event_key in self._delivered:
                return False

            self._delivered[event_key] = DeliveryRecord(
                event_key=event_key,
                recipient_id=recipient_id,
                delivered_at=datetime.now(UTC),
            )
            return True

    def delivered(self, event_key: str) -> bool:
        with self._lock:
            return event_key in self._delivered

    def clear(self) -> None:
        with self._lock:
            self._delivered.clear()
