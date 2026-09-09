from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission, require_tenant_match
from app.core.config import settings as app_settings
from app.core.db import get_db
from app.models.entities import TenantBranding, TenantSettings
from app.services.audit import audit_sensitive

r = APIRouter(prefix="/settings", tags=["settings"])


@r.get("")
async def get_settings(
    tenant_id: int,
    claims=Depends(require_permission("settings.read")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    tenant_settings = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    branding = await db.scalar(
        select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
    )
    return {
        "tenant_id": tenant_id,
        "activation_fee_toman": app_settings.activation_fee_toman,
        "settings": tenant_settings.settings if tenant_settings else {},
        "branding": {
            "logo_url": branding.logo_url if branding else None,
            "primary_color": branding.primary_color if branding else None,
            "display_name": branding.display_name if branding else None,
        },
    }


@r.put("")
async def update_settings(
    tenant_id: int,
    payload: dict[str, Any] = Body(...),
    claims=Depends(require_permission("settings.write")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    allowed_settings = {"currency", "support_username", "support_url", "referral_percent"}
    requested = payload.get("settings", {})
    if not isinstance(requested, dict):
        raise HTTPException(400, "settings must be an object")
    clean_settings = {
        str(key): value for key, value in requested.items() if str(key) in allowed_settings
    }
    if len(clean_settings) != len(requested):
        raise HTTPException(400, "unsupported setting")

    row = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    if row is None:
        row = TenantSettings(tenant_id=tenant_id, settings=clean_settings)
        db.add(row)
    else:
        row.settings = clean_settings

    branding_payload = payload.get("branding", {})
    if branding_payload and not isinstance(branding_payload, dict):
        raise HTTPException(400, "branding must be an object")
    branding = await db.scalar(
        select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
    )
    if branding is None:
        branding = TenantBranding(tenant_id=tenant_id)
        db.add(branding)
    branding.logo_url = str(branding_payload.get("logo_url", branding.logo_url or ""))[:500] or None
    branding.primary_color = str(
        branding_payload.get("primary_color", branding.primary_color or "")
    )[:20] or None
    branding.display_name = str(
        branding_payload.get("display_name", branding.display_name or "")
    )[:150] or None

    audit_sensitive(
        db,
        action="tenant.update",
        tenant_id=tenant_id,
        actor_type="admin",
        actor_id=claims.get("user_id") or claims.get("sub"),
        target_type="tenant_settings",
        target_id=tenant_id,
        metadata={"settings_keys": sorted(clean_settings), "branding_updated": bool(branding_payload)},
    )
    await db.commit()
    return await get_settings(tenant_id=tenant_id, claims=claims, db=db)
