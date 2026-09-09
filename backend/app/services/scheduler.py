from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.entities import Notification, Service

log = logging.getLogger("3xshop.scheduler")


async def _add_notification(
    db,
    *,
    service: Service,
    kind: str,
    title: str,
    body: str,
    idempotency_key: str,
) -> bool:
    existing = await db.scalar(
        select(Notification.id).where(Notification.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return False
    db.add(
        Notification(
            tenant_id=service.tenant_id,
            user_id=service.user_id,
            kind=kind,
            title=title,
            body=body,
            idempotency_key=idempotency_key,
        )
    )
    return True


async def process_expiries() -> None:
    now = datetime.now(UTC)
    warning_limit = now + timedelta(days=3)
    async with SessionLocal() as db:
        services = list(
            (
                await db.scalars(
                    select(Service).where(
                        Service.status.in_(["active", "provisioning"])
                    )
                )
            ).all()
        )
        changed = False
        for service in services:
            metadata = dict(service.metadata_json or {})
            if (
                service.expires_at
                and service.expires_at <= now
                and service.status == "active"
            ):
                service.status = "expired"
                added = await _add_notification(
                    db,
                    service=service,
                    kind="service_expired",
                    title="سرویس منقضی شد",
                    body=f"سرویس #{service.id} منقضی شده است.",
                    idempotency_key=f"service-expired:{service.id}",
                )
                metadata["expiry_notified"] = True
                changed = changed or added or service.status == "expired"
                service.metadata_json = metadata
            elif (
                service.expires_at
                and service.expires_at <= warning_limit
                and not metadata.get("expiry_warning_sent")
            ):
                added = await _add_notification(
                    db,
                    service=service,
                    kind="service_expiry_warning",
                    title="هشدار انقضای سرویس",
                    body=f"سرویس #{service.id} کمتر از ۳ روز دیگر منقضی می‌شود.",
                    idempotency_key=f"service-expiry-warning:{service.id}",
                )
                metadata["expiry_warning_sent"] = True
                service.metadata_json = metadata
                changed = changed or added or True
        if changed:
            await db.commit()


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await process_expiries()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("scheduler cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=300)
        except TimeoutError:
            continue
