from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Coupon
from app.services.coupons import calculate_coupon_for_order
from app.wallet_coupon_referral_contract import money

router = APIRouter(prefix="/coupons", tags=["coupons"])
r = router


class CouponCreate(BaseModel):
    tenant_id: int = Field(gt=0)
    code: str = Field(min_length=2, max_length=60)
    kind: str = Field(pattern="^(fixed|percentage)$")
    value: Decimal = Field(ge=0)
    max_discount: Decimal | None = Field(default=None, ge=0)
    min_purchase: Decimal = Field(default=0, ge=0)
    usage_limit: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None


@router.post("/validate")
async def validate_coupon(
    tenant_id: int,
    code: str,
    subtotal: float,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    try:
        coupon, discount = await calculate_coupon_for_order(db, tenant_id, code, subtotal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {
        "code": coupon.code,
        "discount": str(money(discount)),
        "subtotal": str(money(subtotal)),
        "total": str(money(subtotal) - money(discount)),
    }


@router.get("")
async def list_coupons(
    tenant_id: int | None = None,
    claims=Depends(require_permission("coupons.read")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id is not None:
        require_tenant_match(tenant_id, claims)
    elif not claims.get("is_platform_owner"):
        tenant_id = int(claims["tenant_id"])
    query = select(Coupon).order_by(Coupon.id.desc())
    if tenant_id is not None:
        query = query.where(Coupon.tenant_id == tenant_id)
    rows = (await db.scalars(query)).all()
    return [
        {
            "id": c.id,
            "tenant_id": c.tenant_id,
            "code": c.code,
            "kind": c.kind,
            "value": str(c.value),
            "max_discount": str(c.max_discount) if c.max_discount is not None else None,
            "min_purchase": str(c.min_purchase),
            "usage_limit": c.usage_limit,
            "used_count": c.used_count,
            "active": c.active,
            "starts_at": c.starts_at,
            "expires_at": c.expires_at,
        }
        for c in rows
    ]


@router.post("")
async def create_coupon(
    payload: CouponCreate,
    claims=Depends(require_permission("coupons.write")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(payload.tenant_id, claims)
    if payload.expires_at and payload.starts_at and payload.expires_at <= payload.starts_at:
        raise HTTPException(400, "expires_at_must_follow_starts_at")
    existing = await db.scalar(select(Coupon).where(Coupon.tenant_id == payload.tenant_id, Coupon.code == payload.code.strip().upper()))
    if existing:
        raise HTTPException(409, "coupon_exists")
    coupon = Coupon(
        tenant_id=payload.tenant_id,
        code=payload.code.strip().upper(),
        kind=payload.kind,
        value=payload.value,
        max_discount=payload.max_discount,
        min_purchase=payload.min_purchase,
        usage_limit=payload.usage_limit,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        active=True,
    )
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return {"id": coupon.id, "code": coupon.code, "active": coupon.active}


@router.patch("/{coupon_id}")
async def update_coupon(
    coupon_id: int,
    active: bool | None = None,
    value: Decimal | None = Field(default=None, ge=0),
    claims=Depends(require_permission("coupons.write")),
    db: AsyncSession = Depends(get_db),
):
    coupon = await db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(404, "coupon_not_found")
    require_tenant_match(coupon.tenant_id, claims)
    if active is not None:
        coupon.active = active
    if value is not None:
        coupon.value = value
    await db.commit()
    return {"id": coupon.id, "active": coupon.active, "value": str(coupon.value)}
