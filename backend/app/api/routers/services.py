from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.core.db import get_db
from app.models.entities import Service

r = APIRouter(prefix="/services", tags=["services"])


def _admin(claims: dict) -> bool:
    return bool(claims.get("is_platform_owner")) or "services.write" in claims.get("permissions", []) or "services.read" in claims.get("permissions", [])


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
    service = await db.scalar(select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id))
    if service is None:
        raise HTTPException(404, "service_not_found")
    current_user = int(claims.get("user_id") or claims.get("sub"))
    if not _admin(claims) and service.user_id != current_user:
        raise HTTPException(403, "forbidden")
    return _serialize(service)
