from decimal import Decimal

from app.services.coupons import calculate_coupon_discount


def test_percentage_coupon_discount():
    discount = calculate_coupon_discount(
        Decimal("500"),
        "percent",
        Decimal("10"),
    )
    assert discount == Decimal("50.00")


def test_fixed_coupon_discount():
    discount = calculate_coupon_discount(
        Decimal("500"),
        "fixed",
        Decimal("100"),
    )
    assert discount == Decimal("100.00")


def test_minimum_purchase_rule():
    discount = calculate_coupon_discount(
        Decimal("99"),
        "percent",
        Decimal("10"),
        minimum_purchase=Decimal("100"),
    )
    assert discount == Decimal("0.00")


def test_maximum_discount_rule():
    discount = calculate_coupon_discount(
        Decimal("1000"),
        "percent",
        Decimal("20"),
        maximum_discount=Decimal("100"),
    )
    assert discount == Decimal("100.00")


def test_percentage_above_100_is_rejected():
    try:
        calculate_coupon_discount(
            Decimal("500"),
            "percent",
            Decimal("101"),
        )
    except ValueError as exc:
        assert "cannot exceed 100" in str(exc)
    else:
        raise AssertionError("percentage > 100 must be rejected")
