from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class SchedulerError(Exception):
    pass


class JobType(StrEnum):
    EXPIRY_WARNING = "expiry_warning"
    EXPIRY = "expiry"
    SERVICE_STATUS = "service_status"
    PENDING_NOTIFICATIONS = "pending_notifications"


@dataclass(frozen=True)
class SchedulerJob:
    job_type: JobType
    run_key: str
    scheduled_at: datetime

    def __post_init__(self) -> None:
        if not self.run_key:
            raise SchedulerError("Scheduler run key is required")

        if self.scheduled_at.tzinfo is None:
            raise SchedulerError("Scheduler datetime must be timezone-aware")


def utc_now() -> datetime:
    return datetime.now(UTC)


def build_run_key(
    job_type: JobType,
    tenant_id: int,
    entity_id: int,
    period: str,
) -> str:
    if tenant_id <= 0 or entity_id <= 0:
        raise SchedulerError("Invalid scheduler scope")

    return f"{job_type.value}:{tenant_id}:{entity_id}:{period}"
