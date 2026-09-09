from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Tenant, TenantBranding, TenantSettings

r = APIRouter(prefix="/tenants", tags=["tenants"])


@r.get("")
async def list_tenants(
    claims=Depends(require_permission("tenants.read")),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Tenant)
        .where(Tenant.is_deleted.is_(False))
        .order_by(Tenant.created_at.desc())
    )
    if not claims.get("is_platform_owner"):
        query = query.where(Tenant.id == int(claims["tenant_id"]))
    result = await db.execute(query)
    return [
        {"id": t.id, "slug": t.slug, "name": t.name, "status": t.status, "created_at": t.created_at}
        for t in result.scalars().all()
    ]


@r.get("/{tenant_id}")
async def get_tenant(
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    if "tenants.read" not in claims.get("permissions", []):
        raise HTTPException(403, "forbidden")
    require_tenant_match(tenant_id, claims)
    tenant = await db.scalar(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_deleted.is_(False),
        )
    )
    if not tenant:
        raise HTTPException(404, "tenant not found")
    branding = await db.scalar(
        select(TenantBranding).where(TenantBranding.tenant_id == tenant.id)
    )
    tenant_settings = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at,
        "branding": {
            "logo_url": branding.logo_url if branding else None,
            "primary_color": branding.primary_color if branding else None,
            "display_name": branding.display_name if branding else tenant.name,
        },
        "settings": tenant_settings.settings if tenant_settings else {},
    }
