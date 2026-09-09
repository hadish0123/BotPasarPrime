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


def _username(user: User, order_id: int) -> str:
    base = (user.username or f"user{user.id}").strip().lower()
    safe = "".join(ch for ch in base if ch.isalnum() or ch in "_-")[:40]
    return f"{safe or 'user'}-{order_id}"


def _password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _credentials(db: AsyncSession, tenant_id: int) -> PasarGuardCredentials:
    rows = await db.scalars(select(TenantCredential).where(TenantCredential.tenant_id == tenant_id, TenantCredential.kind.in_(["pasarguard_api_token", "pasarguard_login_url", "pasarguard_username"])))
    values = {row.kind: box.decrypt(row.encrypted_value) for row in rows}
    try:
        return PasarGuardCredentials(base_url=values["pasarguard_login_url"], api_token=values["pasarguard_api_token"], username=values["pasarguard_username"])
    except KeyError as exc:
        raise ValueError("PasarGuard credentials are incomplete") from exc


async def provision_service_for_order(db: AsyncSession, *, tenant_id: int, order_id: int, user_id: int, duration_days: int, quota_gb: int | None) -> Service:
    service = await db.scalar(select(Service).where(Service.tenant_id == tenant_id, Service.user_id == user_id, Service.metadata_json["order_id"].as_integer() == order_id))
    if service is not None and service.status == "active":
        return service
    if service is None:
        service = Service(tenant_id=tenant_id, user_id=user_id, status="provisioning", metadata_json={"order_id": order_id, "duration_days": duration_days, "quota_gb": quota_gb})
        db.add(service)
        await db.flush()
    else:
        service.status = "provisioning"
        service.metadata_json = {**(service.metadata_json or {}), "duration_days": duration_days, "quota_gb": quota_gb}

    user = await db.get(User, user_id)
    if user is None:
        service.status = "failed"
        await db.flush()
        raise ValueError("service user not found")

    client = PasarGuardClient(await _credentials(db, tenant_id), timeout_seconds=settings.pasarguard_timeout_seconds)
    remote_username = _username(user, order_id)
    payload = {
        "username": remote_username,
        "password": _password(),
        "data_limit": quota_gb * 1024**3 if quota_gb is not None else None,
        "expire": int((datetime.now(UTC) + timedelta(days=duration_days)).timestamp()),
    }
    try:
        response = await client.create_user(payload)
    except Exception:
        service.status = "failed"
        await db.flush()
        raise

    external_id = response.get("id") or response.get("username") or response.get("user_id") if isinstance(response, dict) else None
    service.external_id = str(external_id or remote_username)
    service.status = "active"
    service.expires_at = datetime.now(UTC) + timedelta(days=duration_days)
    service.metadata_json = {**(service.metadata_json or {}), "external_username": remote_username}
    await db.flush()
    return service
