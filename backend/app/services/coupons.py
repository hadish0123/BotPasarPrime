from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Coupon
from app.wallet_coupon_referral_contract import (
    calculate_coupon_discount,
    money,
)


def _coupon_kind(coupon) -> str:
    return str(getattr(coupon, "kind", "fixed")).strip().lower()


def _starts_at(coupon):
    return getattr(coupon, "starts_at", None)


def _expires_at(coupon):
    return getattr(coupon, "expires_at", None)


def validate_coupon_window(coupon):
    now = datetime.now(UTC)

    starts_at = _starts_at(coupon)
    expires_at = _expires_at(coupon)

    if starts_at and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)

    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if starts_at and now < starts_at:
        raise ValueError("coupon_not_started")

    if expires_at and now >= expires_at:
        raise ValueError("coupon_expired")

    if starts_at and expires_at and expires_at <= starts_at:
        raise ValueError("invalid_coupon_window")


async def get_coupon(
    db: AsyncSession,
    tenant_id: int,
    code: str,
):
    return await db.scalar(
        select(Coupon).where(
            Coupon.tenant_id == tenant_id,
            Coupon.code == code.strip().upper(),
            Coupon.active.is_(True),
        )
    )


async def calculate_coupon_for_order(
    db: AsyncSession,
    tenant_id: int,
    code: str,
    subtotal,
):
    coupon = await get_coupon(
        db,
        tenant_id,
        code,
    )

    if not coupon:
        raise ValueError("coupon_not_found")

    validate_coupon_window(coupon)

    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise ValueError("coupon_usage_limit_reached")

    discount = calculate_coupon_discount(
        subtotal=subtotal,
        coupon_type=_coupon_kind(coupon),
        coupon_value=coupon.value,
        minimum_purchase=coupon.min_purchase,
        maximum_discount=coupon.max_discount,
    )

    return coupon, discount


async def consume_coupon(
    db: AsyncSession,
    tenant_id: int,
    coupon_id: int,
):
    coupon = await db.scalar(
        select(Coupon).where(
            Coupon.id == coupon_id,
            Coupon.tenant_id == tenant_id,
        )
    )

    if not coupon:
        raise ValueError("coupon_not_found")

    validate_coupon_window(coupon)

    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise ValueError("coupon_usage_limit_reached")

    coupon.used_count += 1

    await db.flush()

    return coupon


def coupon_snapshot(coupon):
    return {
        "tenant_id": coupon.tenant_id,
        "code": coupon.code,
        "kind": _coupon_kind(coupon),
        "value": str(money(coupon.value)),
        "min_purchase": str(money(coupon.min_purchase)),
        "max_discount": (
            str(money(coupon.max_discount)) if coupon.max_discount is not None else None
        ),
        "usage_limit": coupon.usage_limit,
        "used_count": coupon.used_count,
        "active": coupon.active,
        "starts_at": (coupon.starts_at.isoformat() if coupon.starts_at else None),
        "expires_at": (coupon.expires_at.isoformat() if coupon.expires_at else None),
    }
