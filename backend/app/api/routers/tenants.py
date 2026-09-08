from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TenantCreate
from app.core.db import get_db
from app.models.entities import Tenant, TenantBranding, TenantSettings

r = APIRouter(prefix="/tenants", tags=["tenants"])


@r.get("")
async def list_tenants(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Tenant).where(Tenant.is_deleted.is_(False)).order_by(Tenant.created_at.desc())
    )

    return [
        {
            "id": tenant.id,
            "slug": tenant.slug,
            "name": tenant.name,
            "status": tenant.status,
            "created_at": tenant.created_at,
        }
        for tenant in result.scalars().all()
    ]


@r.get("/{tenant_id}")
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)

    if not tenant or tenant.is_deleted:
        raise HTTPException(404, "tenant not found")

    branding_result = await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == tenant.id)
    )
    branding = branding_result.scalar_one_or_none()

    settings_result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    tenant_settings = settings_result.scalar_one_or_none()

    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at,
        "branding": {
            "logo_url": branding.logo_url if branding else None,
            "primary_color": (branding.primary_color if branding else None),
            "display_name": (branding.display_name if branding else tenant.name),
        },
        "settings": (tenant_settings.settings if tenant_settings else {}),
    }


@r.post("")
async def create(
    x: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    # Legacy API endpoint retained for compatibility.
    # Full onboarding must provide Telegram identity and credentials.
    raise HTTPException(
        400,
        "Use the central bot onboarding flow for tenant creation",
    )
