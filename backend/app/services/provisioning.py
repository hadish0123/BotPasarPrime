from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Service, TenantCredential, User
from app.pasarguard.base import PasarGuardCredentials
from app.pasarguard.client import PasarGuardClient
from app.security.crypto import box

MAX_PROVISION_RETRIES = 3


def _username(user: User, order_id: int) -> str:
    base = (user.username or f"user{user.id}").strip().lower()
    safe = "".join(ch for ch in base if ch.isalnum() or ch in "_-")[:40]
    return f"{safe or 'user'}-{order_id}"


def _password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _credentials(db: AsyncSession, tenant_id: int) -> PasarGuardCredentials:
    rows = await db.scalars(
        select(TenantCredential).where(
            TenantCredential.tenant_id == tenant_id,
            TenantCredential.kind.in_(
                ["pasarguard_api_token", "pasarguard_login_url", "pasarguard_username"]
            ),
        )
    )
    values = {row.kind: box.decrypt(row.encrypted_value) for row in rows}
    try:
        return PasarGuardCredentials(
            base_url=values["pasarguard_login_url"],
            api_token=values["pasarguard_api_token"],
            username=values["pasarguard_username"],
        )
    except KeyError as exc:
        raise ValueError("PasarGuard credentials are incomplete") from exc


async def _mark_provisioning_failed(db: AsyncSession, service: Service, exc: Exception) -> None:
    metadata = dict(service.metadata_json or {})
    attempts = int(metadata.get("provision_attempts", 0))
    service.status = "provisioning_failed"
    service.metadata_json = {
        **metadata,
        "provision_attempts": attempts,
        "last_error": type(exc).__name__,
        "retryable": attempts < MAX_PROVISION_RETRIES,
        "failed_at": datetime.now(UTC).isoformat(),
    }
    await db.flush()
    await db.commit()


async def provision_service_for_order(
    db: AsyncSession,
    *,
    tenant_id: int,
    order_id: int,
    user_id: int,
    plan_id: int,
    duration_days: int,
    quota_gb: int | None,
) -> Service:
    service = await db.scalar(
        select(Service).where(
            Service.tenant_id == tenant_id,
            Service.user_id == user_id,
            Service.metadata_json["order_id"].as_integer() == order_id,
        )
    )
    if service is not None and service.status == "active":
        return service

    metadata = {
        "order_id": order_id,
        "plan_id": plan_id,
        "duration_days": duration_days,
        "quota_gb": quota_gb,
    }
    if service is None:
        service = Service(
            tenant_id=tenant_id,
            user_id=user_id,
            status="provisioning",
            metadata_json={**metadata, "provision_attempts": 1},
        )
        db.add(service)
        await db.flush()
    else:
        old = dict(service.metadata_json or {})
        attempts = int(old.get("provision_attempts", 0))
        if attempts >= MAX_PROVISION_RETRIES:
            raise ValueError("provision_retry_limit_reached")
        service.status = "provisioning"
        service.metadata_json = {
            **old,
            **metadata,
            "provision_attempts": attempts + 1,
            "retryable": False,
        }

    try:
        user = await db.get(User, user_id)
        if user is None:
            raise ValueError("service user not found")

        client = PasarGuardClient(
            await _credentials(db, tenant_id),
            timeout_seconds=settings.pasarguard_timeout_seconds,
        )
        remote_username = _username(user, order_id)
        expires_at = datetime.now(UTC) + timedelta(days=duration_days)
        payload = {
            "username": remote_username,
            "password": _password(),
            "data_limit": quota_gb * 1024**3 if quota_gb is not None else None,
            "expire": int(expires_at.timestamp()),
        }
        response = await client.create_user(payload)
    except Exception as exc:
        await _mark_provisioning_failed(db, service, exc)
        raise

    external_id = None
    if isinstance(response, dict):
        external_id = response.get("id") or response.get("username") or response.get("user_id")
    service.external_id = str(external_id or remote_username)
    service.status = "active"
    service.expires_at = expires_at
    service.metadata_json = {
        **(service.metadata_json or {}),
        "external_username": remote_username,
        "retryable": False,
        "last_error": None,
    }
    await db.flush()
    return service


async def renew_service(
    db: AsyncSession,
    *,
    tenant_id: int,
    service_id: int,
    duration_days: int,
    quota_gb: int | None = None,
) -> Service:
    if duration_days < 1 or duration_days > 3650:
        raise ValueError("invalid_duration_days")
    service = await db.scalar(
        select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id)
    )
    if service is None:
        raise ValueError("service_not_found")
    if service.status in {"revoked", "refunded"}:
        raise ValueError("service_not_renewable")
    if not service.external_id:
        raise ValueError("service_external_id_missing")

    now = datetime.now(UTC)
    current_expiry = service.expires_at if service.expires_at and service.expires_at > now else now
    new_expiry = current_expiry + timedelta(days=duration_days)
    payload = {"expire": int(new_expiry.timestamp())}
    if quota_gb is not None:
        if quota_gb < 1:
            raise ValueError("invalid_quota_gb")
        payload["data_limit"] = quota_gb * 1024**3

    client = PasarGuardClient(
        await _credentials(db, tenant_id),
        timeout_seconds=settings.pasarguard_timeout_seconds,
    )
    try:
        await client.renew_subscription(
            service.external_id,
            expire=int(new_expiry.timestamp()),
            data_limit=payload.get("data_limit"),
        )
    except Exception as exc:
        service.metadata_json = {
            **(service.metadata_json or {}),
            "last_renewal_error": type(exc).__name__,
            "renewal_retryable": True,
        }
        await db.flush()
        raise
    service.status = "active"
    service.expires_at = new_expiry
    service.metadata_json = {
        **(service.metadata_json or {}),
        "last_renewed_at": now.isoformat(),
        "last_renewal_days": duration_days,
        "renewal_retryable": False,
        **({"quota_gb": quota_gb} if quota_gb is not None else {}),
    }
    await db.flush()
    return service


async def revoke_service(db: AsyncSession, *, tenant_id: int, service_id: int) -> Service:
    service = await db.scalar(select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id))
    if service is None:
        raise ValueError("service_not_found")
    if service.status in {"revoked", "refunded", "expired"}:
        return service
    if not service.external_id:
        raise ValueError("service_external_id_missing")
    client = PasarGuardClient(
        await _credentials(db, tenant_id),
        timeout_seconds=settings.pasarguard_timeout_seconds,
    )
    await client.delete_user(service.external_id)
    service.status = "revoked"
    service.metadata_json = {**(service.metadata_json or {}), "revoked_at": datetime.now(UTC).isoformat()}
    await db.flush()
    return service


async def get_service_subscription(db: AsyncSession, *, tenant_id: int, service_id: int) -> object:
    service = await db.scalar(select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id))
    if service is None:
        raise ValueError("service_not_found")
    if not service.external_id:
        raise ValueError("service_external_id_missing")
    client = PasarGuardClient(
        await _credentials(db, tenant_id),
        timeout_seconds=settings.pasarguard_timeout_seconds,
    )
    return await client.get_subscription(service.external_id)
