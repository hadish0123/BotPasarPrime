from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Service
from app.services.provisioning import get_service_subscription, renew_service, revoke_service

r = APIRouter(prefix="/services", tags=["services"])


def _admin(claims: dict) -> bool:
    return bool(claims.get("is_platform_owner")) or "services.write" in claims.get("permissions", [])


def _serialize(service: Service) -> dict:
    return {
        "id": service.id,
        "tenant_id": service.tenant_id,
        "user_id": service.user_id,
        "external_id": service.external_id,
        "status": service.status,
        "expires_at": service.expires_at,
        "metadata": service.metadata_json or {},
    }


class RenewalRequest(BaseModel):
    duration_days: int = Field(ge=1, le=3650)
    quota_gb: int | None = Field(default=None, ge=1, le=10_000_000)


async def _get_owned_service(
    db: AsyncSession, service_id: int, tenant_id: int, claims: dict
) -> Service:
    service = await db.scalar(
        select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id)
    )
    if service is None:
        raise HTTPException(404, "service_not_found")
    current_user = int(claims.get("user_id") or claims.get("sub"))
    if not _admin(claims) and service.user_id != current_user:
        raise HTTPException(403, "forbidden")
    return service


@r.get("")
async def list_services(
    tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)
):
    require_tenant_match(tenant_id, claims)
    current_user = int(claims.get("user_id") or claims.get("sub"))
    query = (
        select(Service)
        .where(Service.tenant_id == tenant_id)
        .order_by(Service.id.desc())
        .limit(100)
    )
    if not _admin(claims):
        query = query.where(Service.user_id == current_user)
    result = await db.execute(query)
    return [_serialize(item) for item in result.scalars().all()]


@r.get("/{service_id}")
async def read_service(
    service_id: int, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)
):
    require_tenant_match(tenant_id, claims)
    return _serialize(await _get_owned_service(db, service_id, tenant_id, claims))


@r.get("/{service_id}/subscription")
async def subscription(
    service_id: int, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)
):
    require_tenant_match(tenant_id, claims)
    await _get_owned_service(db, service_id, tenant_id, claims)
    try:
        return await get_service_subscription(db, tenant_id=tenant_id, service_id=service_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "pasarguard_subscription_failed") from exc


@r.post("/{service_id}/renew")
async def renew(
    service_id: int,
    tenant_id: int,
    payload: RenewalRequest,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    await _get_owned_service(db, service_id, tenant_id, claims)
    try:
        result = await renew_service(
            db,
            tenant_id=tenant_id,
            service_id=service_id,
            duration_days=payload.duration_days,
            quota_gb=payload.quota_gb,
        )
        await db.commit()
        return _serialize(result)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, "pasarguard_renewal_failed") from exc


@r.post("/{service_id}/revoke")
async def revoke(
    service_id: int,
    tenant_id: int,
    claims=Depends(require_permission("services.write")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    try:
        result = await revoke_service(db, tenant_id=tenant_id, service_id=service_id)
        await db.commit()
        return _serialize(result)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, "pasarguard_revoke_failed") from exc
