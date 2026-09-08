from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class DiscountKind(StrEnum):
    NONE = "none"
    PERCENT = "percent"
    FIXED = "fixed"


@dataclass(frozen=True)
class PriceResult:
    base_price: Decimal
    discount: Decimal
    final_price: Decimal


@dataclass(frozen=True)
class PlanSnapshot:
    product_name: str
    plan_name: str
    price: Decimal
    duration_days: int
    quota_gb: int | None
    category: str | None


def calculate_price(
    base_price,
    discount_kind: str = "none",
    discount_value=0,
) -> PriceResult:
    base = Decimal(str(base_price))

    if base < 0:
        raise ValueError("price cannot be negative")

    kind = (discount_kind or "none").lower()
    value = Decimal(str(discount_value or 0))

    if value < 0:
        raise ValueError("discount cannot be negative")

    if kind == DiscountKind.NONE:
        discount = Decimal("0.00")

    elif kind == DiscountKind.PERCENT:
        if value > 100:
            raise ValueError("percent discount cannot exceed 100")
        discount = (base * value / Decimal("100")).quantize(Decimal("0.01"))

    elif kind == DiscountKind.FIXED:
        discount = min(value, base).quantize(Decimal("0.01"))

    else:
        raise ValueError("invalid discount kind")

    final = (base - discount).quantize(Decimal("0.01"))

    return PriceResult(
        base_price=base.quantize(Decimal("0.01")),
        discount=discount,
        final_price=final,
    )


def shop_snapshot() -> dict:
    return {
        "categories": True,
        "products": True,
        "plans": True,
        "volume": True,
        "duration": True,
        "dynamic_pricing": True,
        "discounts": True,
        "activation_toggle": True,
        "order_snapshot": True,
        "hardcoded_prices": False,
    }
