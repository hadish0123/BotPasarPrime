from datetime import UTC, datetime

from app.notifications.contracts import (
    NOTIFICATION_TYPES,
    NotificationEvent,
    NotificationType,
    build_event_key,
    notification_snapshot,
    validate_event,
)
from app.notifications.idempotency import NotificationDeliveryLedger
from app.notifications.service import NotificationService
from app.scheduler.contracts import (
    JobType,
    SchedulerJob,
    build_run_key,
)
from app.scheduler.runner import IdempotentScheduler

print("PAGE 16 NOTIFICATIONS & SCHEDULER CONTRACT: START")

required = {
    NotificationType.TENANT_REQUEST_CREATED,
    NotificationType.TENANT_REQUEST_APPROVED,
    NotificationType.TENANT_REQUEST_REJECTED,
    NotificationType.PAYMENT_SUCCESS,
    NotificationType.PAYMENT_REJECTED,
    NotificationType.PURCHASE_SUCCESS,
    NotificationType.SERVICE_EXPIRING,
    NotificationType.SERVICE_EXPIRED,
    NotificationType.TICKET_REPLY,
    NotificationType.SERVICE_STATUS_CHANGED,
}

assert required.issubset(set(NOTIFICATION_TYPES))
print("NOTIFICATION_EVENTS: 10")

event_key = build_event_key(
    NotificationType.PAYMENT_SUCCESS,
    recipient_id=10,
    entity_id=20,
)

event = NotificationEvent(
    event_key=event_key,
    notification_type=NotificationType.PAYMENT_SUCCESS,
    recipient_id=10,
    tenant_id=1,
    entity_id=20,
)

validate_event(event)
print("EVENT_VALIDATION: READY")

ledger = NotificationDeliveryLedger()

assert ledger.claim("event-1", 10) is True
assert ledger.claim("event-1", 10) is False
assert ledger.delivered("event-1") is True

print("PROCESS_IDEMPOTENCY: ENABLED")
print("DUPLICATE_DELIVERY: BLOCKED")


class Sender:
    def __init__(self):
        self.calls = []

    def send(self, recipient_id, notification_type, payload=None):
        self.calls.append(
            (recipient_id, notification_type.value)
        )


sender = Sender()
service = NotificationService(sender)

first = service.dispatch(event)
second = service.dispatch(event)

assert first.sent is True
assert first.duplicate is False
assert second.sent is False
assert second.duplicate is True
assert len(sender.calls) == 1

print("NOTIFICATION_DISPATCH: READY")
print("REPEATED_EVENT: BLOCKED")

scheduler = IdempotentScheduler()
claims = set()
runs = []


def claim(run_key):
    if run_key in claims:
        return False
    claims.add(run_key)
    return True


run_key = build_run_key(
    JobType.EXPIRY_WARNING,
    tenant_id=1,
    entity_id=99,
    period="2026-09-08",
)

job = SchedulerJob(
    job_type=JobType.EXPIRY_WARNING,
    run_key=run_key,
    scheduled_at=datetime.now(UTC),
)

assert scheduler.run_once(
    job.run_key,
    claim,
    lambda: runs.append(job.run_key),
) is True

assert scheduler.run_once(
    job.run_key,
    claim,
    lambda: runs.append(job.run_key),
) is False

assert len(runs) == 1

print("SCHEDULER: READY")
print("SCHEDULER_IDEMPOTENCY: ENABLED")
print("SCHEDULER_DUPLICATE_RUN: BLOCKED")

snapshot = notification_snapshot()

assert snapshot["idempotent_scheduler"] is True
assert snapshot["duplicate_delivery"] is False
assert snapshot["tenant_scoped"] is True

print("PERSISTENT_DELIVERY_LEDGER: REQUIRED")
print("PERSISTENT_SCHEDULER_LEDGER: REQUIRED")
print("TENANT_SCOPING: ENABLED")
print("PAGE 16 NOTIFICATIONS & SCHEDULER CONTRACT: OK")
