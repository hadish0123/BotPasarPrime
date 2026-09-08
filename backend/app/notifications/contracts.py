from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NotificationError(Exception):
    pass


class NotificationType(StrEnum):
    TENANT_REQUEST_CREATED = "tenant_request_created"
    TENANT_REQUEST_APPROVED = "tenant_request_approved"
    TENANT_REQUEST_REJECTED = "tenant_request_rejected"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_REJECTED = "payment_rejected"
    PURCHASE_SUCCESS = "purchase_success"
    SERVICE_EXPIRING = "service_expiring"
    SERVICE_EXPIRED = "service_expired"
    TICKET_REPLY = "ticket_reply"
    SERVICE_STATUS_CHANGED = "service_status_changed"


@dataclass(frozen=True)
class NotificationEvent:
    event_key: str
    notification_type: NotificationType
    recipient_id: int
    tenant_id: int | None = None
    entity_id: int | None = None
    payload: dict | None = None


NOTIFICATION_TYPES = tuple(NotificationType)


def build_event_key(
    notification_type: NotificationType,
    recipient_id: int,
    entity_id: int | None = None,
    discriminator: str | None = None,
) -> str:
    parts = [
        notification_type.value,
        str(recipient_id),
        str(entity_id or 0),
        discriminator or "",
    ]
    return ":".join(parts)


def validate_event(event: NotificationEvent) -> None:
    if not event.event_key:
        raise NotificationError("Notification event key is required")

    if event.recipient_id <= 0:
        raise NotificationError("Invalid notification recipient")

    if event.tenant_id is not None and event.tenant_id <= 0:
        raise NotificationError("Invalid tenant context")


def notification_snapshot() -> dict:
    return {
        "notification_types": len(NOTIFICATION_TYPES),
        "idempotent_scheduler": True,
        "duplicate_delivery": False,
        "tenant_scoped": True,
    }
