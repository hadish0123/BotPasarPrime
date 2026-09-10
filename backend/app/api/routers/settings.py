from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission, require_tenant_match
from app.core.config import settings as app_settings
from app.core.db import get_db
from app.models.entities import Tenant, TenantBranding, TenantSettings
from app.security.crypto import box
from app.services.audit import audit_sensitive

r = APIRouter(prefix="/settings", tags=["settings"])
_PLATFORM_SLUG = "__platform__"


async def _platform_row(db: AsyncSession) -> TenantSettings:
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == _PLATFORM_SLUG))
    if tenant is None:
        tenant = Tenant(slug=_PLATFORM_SLUG, name="Platform", status="system", is_deleted=True)
        db.add(tenant)
        await db.flush()
    row = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))
    if row is None:
        row = TenantSettings(
            tenant_id=tenant.id,
            settings={"activation_fee_toman": int(app_settings.activation_fee_toman)},
        )
        db.add(row)
        await db.flush()
    return row


def _decrypt(value: Any) -> str:
    if not value:
        return ""
    try:
        return box.decrypt(str(value))
    except Exception:
        return ""


async def get_platform_payment_config(db: AsyncSession) -> dict[str, Any]:
    row = await _platform_row(db)
    data = row.settings or {}
    return {
        "activation_fee_toman": int(data.get("activation_fee_toman", app_settings.activation_fee_toman)),
        "card_number": _decrypt(data.get("encrypted_card_number")),
        "card_holder": _decrypt(data.get("encrypted_card_holder")),
        "bank": _decrypt(data.get("encrypted_bank")),
    }


@r.get("/platform")
async def get_platform_settings(
    claims=Depends(require_permission("settings.read")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "platform_owner_required")
    config = await get_platform_payment_config(db)
    await db.commit()
    return {"manual_payment": config}


@r.put("/platform")
async def update_platform_settings(
    payload: dict[str, Any] = Body(...),
    claims=Depends(require_permission("settings.write")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "platform_owner_required")
    payment = payload.get("manual_payment", payload)
    if not isinstance(payment, dict):
        raise HTTPException(400, "manual_payment must be an object")
    try:
        fee = int(payment.get("activation_fee_toman", app_settings.activation_fee_toman))
    except (TypeError, ValueError):
        raise HTTPException(400, "activation_fee_toman must be an integer") from None
    card_number = str(payment.get("card_number", "")).strip()
    card_holder = str(payment.get("card_holder", "")).strip()
    bank = str(payment.get("bank", "")).strip()
    if fee < 0:
        raise HTTPException(400, "activation fee cannot be negative")
    if fee > 0 and (not card_number or not card_holder):
        raise HTTPException(400, "card number and card holder are required when activation fee is enabled")
    if card_number and (len(card_number) < 12 or len(card_number) > 32):
        raise HTTPException(400, "invalid card number")

    row = await _platform_row(db)
    current = row.settings or {}
    row.settings = {
        **current,
        "activation_fee_toman": fee,
        "encrypted_card_number": box.encrypt(card_number) if card_number else current.get("encrypted_card_number"),
        "encrypted_card_holder": box.encrypt(card_holder) if card_holder else current.get("encrypted_card_holder"),
        "encrypted_bank": box.encrypt(bank) if bank else current.get("encrypted_bank"),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    audit_sensitive(
        db,
        action="settings.platform_payment_update",
        tenant_id=None,
        actor_type="admin",
        actor_id=claims.get("user_id") or claims.get("sub"),
        target_type="platform_settings",
        target_id=1,
        metadata={"activation_fee_toman": fee, "bank_configured": bool(bank), "card_configured": bool(card_number)},
    )
    await db.commit()
    return {"manual_payment": await get_platform_payment_config(db)}


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
    platform = await get_platform_payment_config(db) if claims.get("is_platform_owner") else None
    return {
        "tenant_id": tenant_id,
        "activation_fee_toman": platform["activation_fee_toman"] if platform else app_settings.activation_fee_toman,
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
    allowed_settings = {
        "currency",
        "support_username",
        "support_url",
        "referral_percent",
    }
    requested = payload.get("settings", {})
    if not isinstance(requested, dict):
        raise HTTPException(400, "settings must be an object")
    clean_settings = {
        str(key): value
        for key, value in requested.items()
        if str(key) in allowed_settings
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
        row.settings = {**(row.settings or {}), **clean_settings}

    branding_payload = payload.get("branding", {})
    if branding_payload and not isinstance(branding_payload, dict):
        raise HTTPException(400, "branding must be an object")
    branding = await db.scalar(
        select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
    )
    if branding is None:
        branding = TenantBranding(tenant_id=tenant_id)
        db.add(branding)
    branding.logo_url = (
        str(branding_payload.get("logo_url", branding.logo_url or ""))[:500] or None
    )
    branding.primary_color = (
        str(branding_payload.get("primary_color", branding.primary_color or ""))[:20]
        or None
    )
    branding.display_name = (
        str(branding_payload.get("display_name", branding.display_name or ""))[:150]
        or None
    )

    audit_sensitive(
        db,
        action="tenant.update",
        tenant_id=tenant_id,
        actor_type="admin",
        actor_id=claims.get("user_id") or claims.get("sub"),
        target_type="tenant_settings",
        target_id=tenant_id,
        metadata={
            "settings_keys": sorted(clean_settings),
            "branding_updated": bool(branding_payload),
        },
    )
    await db.commit()
    return await get_settings(tenant_id=tenant_id, claims=claims, db=db)
