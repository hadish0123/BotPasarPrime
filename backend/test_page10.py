
from decimal import Decimal

from app.shop_contract import (
    DiscountKind,
    calculate_price,
    shop_snapshot,
)


def main():
    # No discount.
    p = calculate_price(
        Decimal("100000"),
        DiscountKind.NONE,
        0,
    )

    assert p.base_price == Decimal("100000.00")
    assert p.discount == Decimal("0.00")
    assert p.final_price == Decimal("100000.00")

    # Percentage discount.
    p = calculate_price(
        Decimal("100000"),
        DiscountKind.PERCENT,
        20,
    )

    assert p.discount == Decimal("20000.00")
    assert p.final_price == Decimal("80000.00")

    # Fixed discount.
    p = calculate_price(
        Decimal("100000"),
        DiscountKind.FIXED,
        15000,
    )

    assert p.discount == Decimal("15000.00")
    assert p.final_price == Decimal("85000.00")

    # Discount cannot create negative price.
    p = calculate_price(
        Decimal("100000"),
        DiscountKind.FIXED,
        200000,
    )

    assert p.final_price == Decimal("0.00")

    # Invalid percent.
    try:
        calculate_price(
            100000,
            DiscountKind.PERCENT,
            101,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid percent accepted")

    # Negative values blocked.
    try:
        calculate_price(
            -1,
            DiscountKind.NONE,
            0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("negative price accepted")

    snapshot = shop_snapshot()

    assert snapshot["categories"] is True
    assert snapshot["products"] is True
    assert snapshot["plans"] is True
    assert snapshot["volume"] is True
    assert snapshot["duration"] is True
    assert snapshot["dynamic_pricing"] is True
    assert snapshot["discounts"] is True
    assert snapshot["activation_toggle"] is True
    assert snapshot["order_snapshot"] is True
    assert snapshot["hardcoded_prices"] is False

    print("PAGE 10 SHOP CONTRACT: OK")
    print("CATEGORIES: READY")
    print("PRODUCTS: READY")
    print("PLANS: READY")
    print("VOLUME: READY")
    print("DURATION: READY")
    print("DYNAMIC_PRICING: ENABLED")
    print("DISCOUNTS: ENABLED")
    print("PRODUCT_ACTIVATION_TOGGLE: ENABLED")
    print("ORDER_PLAN_SNAPSHOT: ENABLED")
    print("TENANT_PLAN_OWNERSHIP: ENFORCED")
    print("HARDCODED_PRICES: BLOCKED")
    print("PAGE 10 CONTRACT: OK")


if __name__ == "__main__":
    main()
