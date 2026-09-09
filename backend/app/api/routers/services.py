from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Service
from app.services.audit import audit_sensitive
from app.services.notifications import enqueue
from app.services.provisioning import get_service_subscription, provision_service_for_order, renew_service, revoke_service

r = APIRouter(prefix="/services", tags=["services"])
MAX_PROVISION_RETRIES = 3


def _admin(claims: dict) -> bool:
    return bool(claims.get("is_platform_owner")) or "services.write" in claims.get("permissions", [])


def _serialize(service: Service) -> dict:
    return {"id": service.id, "tenant_id": service.tenant_id, "user_id": service.user_id, "external_id": service.external_id, "status": service.status, "expires_at": service.expires_at, "metadata": service.metadata_json or {}}


class RenewalRequest(BaseModel):
    duration_days: int = Field(ge=1, le=3650)
    quota_gb: int | None = Field(default=None, ge=1, le=10_000_000)


async def _get_owned_service(db: AsyncSession, service_id: int, tenant_id: int, claims: dict) -> Service:
    service = await db.scalar(select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id))
    if service is None:
        raise HTTPException(404, "service_not_found")
    current_user = int(claims.get("user_id") or claims.get("sub"))
    if not _admin(claims) and service.user_id != current_user:
        raise HTTPException(403, "forbidden")
    return service


@r.get("")
async def list_services(tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    current_user = int(claims.get("user_id") or claims.get("sub"))
    query = select(Service).where(Service.tenant_id == tenant_id).order_by(Service.id.desc()).limit(100)
    if not _admin(claims):
        query = query.where(Service.user_id == current_user)
    result = await db.execute(query)
    return [_serialize(item) for item in result.scalars().all()]


@r.get("/{service_id}")
async def read_service(service_id: int, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    return _serialize(await _get_owned_service(db, service_id, tenant_id, claims))


@r.get("/{service_id}/subscription")
async def subscription(service_id: int, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    await _get_owned_service(db, service_id, tenant_id, claims)
    try:
        return await get_service_subscription(db, tenant_id=tenant_id, service_id=service_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "pasarguard_subscription_failed") from exc


@r.post("/{service_id}/retry")
async def retry_provisioning(service_id: int, tenant_id: int, claims=Depends(require_permission("services.write")), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    service = await db.scalar(select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id))
    if service is None:
        raise HTTPException(404, "service_not_found")
    if service.status != "provisioning_failed":
        raise HTTPException(409, "service_not_retryable")
    metadata = dict(service.metadata_json or {})
    retry_count = int(metadata.get("retry_count", 0) or 0)
    if retry_count >= MAX_PROVISION_RETRIES:
        raise HTTPException(409, "provisioning_retry_limit_reached")
    try:
        plan_id = int(metadata["plan_id"])
        duration_days = int(metadata["duration_days"])
        quota_gb = metadata.get("quota_gb")
        quota_gb = int(quota_gb) if quota_gb is not None else None
        attempt = retry_count + 1
        metadata["retry_count"] = attempt
        metadata["last_retry_at"] = datetime.now(UTC).isoformat()
        service.metadata_json = metadata
        await db.flush()
        result = await provision_service_for_order(db, tenant_id=tenant_id, order_id=int(metadata["order_id"]), user_id=service.user_id, plan_id=plan_id, duration_days=duration_days, quota_gb=quota_gb)
        result.metadata_json = {**(result.metadata_json or {}), "retry_count": attempt}
        await enqueue(db, tenant_id=tenant_id, user_id=service.user_id, kind="service_status", title="سرویس فعال شد", body=f"سرویس #{service.id} پس از تلاش مجدد فعال شد.", key=f"service:{service.id}:retry:{attempt}")
        audit_sensitive(db, action="service.retry", tenant_id=tenant_id, actor_type="admin", actor_id=claims.get("user_id") or claims.get("sub"), target_type="service", target_id=service.id, metadata={"attempt": attempt})
        await db.commit()
        return _serialize(result)
    except (KeyError, TypeError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(409, "invalid_provisioning_metadata") from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, "order_fulfillment_failed") from exc


@r.post("/{service_id}/renew")
async def renew(service_id: int, tenant_id: int, payload: RenewalRequest, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    service = await _get_owned_service(db, service_id, tenant_id, claims)
    try:
        result = await renew_service(db, tenant_id=tenant_id, service_id=service_id, duration_days=payload.duration_days, quota_gb=payload.quota_gb)
        await enqueue(db, tenant_id=tenant_id, user_id=service.user_id, kind="service_renewed", title="سرویس تمدید شد", body=f"سرویس #{service.id} با موفقیت تمدید شد.", key=f"service:{service.id}:renewed:{result.expires_at.isoformat() if result.expires_at else 'none'}")
        audit_sensitive(db, action="service.renew", tenant_id=tenant_id, actor_type="user" if not _admin(claims) else "admin", actor_id=claims.get("user_id") or claims.get("sub"), target_type="service", target_id=service.id, metadata={"duration_days": payload.duration_days, "quota_gb": payload.quota_gb})
        await db.commit()
        return _serialize(result)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, "pasarguard_renewal_failed") from exc


@r.post("/{service_id}/revoke")
async def revoke(service_id: int, tenant_id: int, claims=Depends(require_permission("services.write")), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    service = await _get_owned_service(db, service_id, tenant_id, claims)
    try:
        result = await revoke_service(db, tenant_id=tenant_id, service_id=service_id)
        await enqueue(db, tenant_id=tenant_id, user_id=service.user_id, kind="service_status", title="سرویس غیرفعال شد", body=f"سرویس #{service.id} غیرفعال شد.", key=f"service:{service.id}:revoked")
        audit_sensitive(db, action="service.revoke", tenant_id=tenant_id, actor_type="admin", actor_id=claims.get("user_id") or claims.get("sub"), target_type="service", target_id=service.id, metadata={"previous_status": service.status})
        await db.commit()
        return _serialize(result)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, "pasarguard_revoke_failed") from exc
