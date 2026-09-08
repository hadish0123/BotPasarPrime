from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class WalletDirection(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"


class CouponType(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"


class ReferralLedgerType(StrEnum):
    COMMISSION = "commission"


def money(value) -> Decimal:
    try:
        value = Decimal(str(value))
    except Exception as exc:
        raise ValueError("invalid monetary value") from exc

    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if value < 0:
        raise ValueError("monetary value cannot be negative")

    return value


def calculate_coupon_discount(
    subtotal,
    coupon_type: str,
    coupon_value,
    minimum_purchase=0,
    maximum_discount=None,
):
    subtotal = money(subtotal)
    coupon_value = money(coupon_value)
    minimum_purchase = money(minimum_purchase)

    if subtotal < minimum_purchase:
        return Decimal("0.00")

    if coupon_type == CouponType.FIXED.value:
        discount = coupon_value
    elif coupon_type == CouponType.PERCENT.value:
        if coupon_value > 100:
            raise ValueError("coupon percentage cannot exceed 100")
        discount = subtotal * coupon_value / Decimal("100")
    else:
        raise ValueError("invalid coupon type")

    if maximum_discount is not None:
        discount = min(discount, money(maximum_discount))

    return min(discount, subtotal).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def validate_coupon_window(
    starts_at: datetime | None,
    expires_at: datetime | None,
    now: datetime | None = None,
):
    now = now or datetime.now(UTC)

    if starts_at and expires_at and expires_at <= starts_at:
        raise ValueError("coupon expiration must be after start")

    if starts_at and now < starts_at:
        raise ValueError("coupon is not active yet")

    if expires_at and now >= expires_at:
        raise ValueError("coupon has expired")


def validate_referral(referrer_user_id: int, referred_user_id: int):
    if referrer_user_id == referred_user_id:
        raise ValueError("self referral is not allowed")


def calculate_commission(amount, commission_percent):
    amount = money(amount)
    percent = Decimal(str(commission_percent))

    if percent < 0 or percent > 100:
        raise ValueError("invalid commission percentage")

    return (amount * percent / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


@dataclass(frozen=True)
class WalletSnapshot:
    tenant_id: int
    user_id: int
    balance: Decimal


@dataclass(frozen=True)
class CouponSnapshot:
    tenant_id: int
    code: str
    coupon_type: str
    value: Decimal
    minimum_purchase: Decimal
    maximum_discount: Decimal | None
    usage_limit: int | None
    used_count: int


@dataclass(frozen=True)
class ReferralSnapshot:
    tenant_id: int
    referrer_user_id: int
    referred_user_id: int
    code: str


@dataclass(frozen=True)
class ReferralLedgerSnapshot:
    tenant_id: int
    user_id: int
    order_id: int | None
    amount: Decimal
    commission_percent: Decimal
    ledger_type: str = ReferralLedgerType.COMMISSION.value


def wallet_snapshot(wallet) -> WalletSnapshot:
    return WalletSnapshot(
        tenant_id=wallet.tenant_id,
        user_id=wallet.user_id,
        balance=money(wallet.balance),
    )


def coupon_snapshot(coupon) -> CouponSnapshot:
    return CouponSnapshot(
        tenant_id=coupon.tenant_id,
        code=coupon.code,
        coupon_type=coupon.coupon_type,
        value=money(coupon.value),
        minimum_purchase=money(coupon.minimum_purchase),
        maximum_discount=(
            money(coupon.maximum_discount) if coupon.maximum_discount is not None else None
        ),
        usage_limit=coupon.usage_limit,
        used_count=coupon.used_count,
    )


def referral_snapshot(referral) -> ReferralSnapshot:
    return ReferralSnapshot(
        tenant_id=referral.tenant_id,
        referrer_user_id=referral.referrer_user_id,
        referred_user_id=referral.referred_user_id,
        code=referral.code,
    )
