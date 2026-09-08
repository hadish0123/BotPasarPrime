from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.notifications.contracts import (
    NotificationEvent,
    NotificationType,
    validate_event,
)
from app.notifications.idempotency import NotificationDeliveryLedger


class NotificationSender(Protocol):
    def send(
        self,
        recipient_id: int,
        notification_type: NotificationType,
        payload: dict | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class NotificationResult:
    event_key: str
    sent: bool
    duplicate: bool


class NotificationService:
    def __init__(self, sender: NotificationSender) -> None:
        self.sender = sender
        self.ledger = NotificationDeliveryLedger()

    def dispatch(self, event: NotificationEvent) -> NotificationResult:
        validate_event(event)

        if not self.ledger.claim(
            event.event_key,
            event.recipient_id,
        ):
            return NotificationResult(
                event_key=event.event_key,
                sent=False,
                duplicate=True,
            )

        try:
            self.sender.send(
                event.recipient_id,
                event.notification_type,
                event.payload,
            )
        except Exception:
            # Failed deliveries must remain retryable.
            self.ledger._delivered.pop(event.event_key, None)
            raise

        return NotificationResult(
            event_key=event.event_key,
            sent=True,
            duplicate=False,
        )
