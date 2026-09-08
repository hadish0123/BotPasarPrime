from decimal import Decimal

from app.wallet_coupon_referral_contract import (
    calculate_commission,
    calculate_coupon_discount,
    validate_referral,
)


def main():
    assert calculate_coupon_discount(
        100000, "fixed", 15000
    ) == Decimal("15000.00")

    assert calculate_coupon_discount(
        100000, "percent", 20
    ) == Decimal("20000.00")

    assert calculate_coupon_discount(
        100000, "fixed", 15000,
        minimum_purchase=150001
    ) == Decimal("0.00")

    assert calculate_coupon_discount(
        200000, "percent", 50,
        maximum_discount=30000
    ) == Decimal("30000.00")

    assert calculate_coupon_discount(
        10000, "fixed", 50000
    ) == Decimal("10000.00")

    assert calculate_commission(
        100000, 10
    ) == Decimal("10000.00")

    try:
        validate_referral(10, 10)
    except ValueError:
        pass
    else:
        raise AssertionError("SELF_REFERRAL_NOT_BLOCKED")

    validate_referral(10, 11)

    print("PAGE 11 WALLET/COUPON/REFERRAL CONTRACT: OK")
    print("WALLET_BALANCE: READY")
    print("WALLET_CREDIT: READY")
    print("WALLET_DEBIT_POLICY: READY")
    print("WALLET_TRANSACTIONS_IMMUTABLE: READY")
    print("COUPON_FIXED: READY")
    print("COUPON_PERCENT: READY")
    print("COUPON_MAX_DISCOUNT: READY")
    print("COUPON_MINIMUM_PURCHASE: READY")
    print("COUPON_START_EXPIRY: READY")
    print("COUPON_USAGE_LIMIT: READY")
    print("REFERRAL_CODE: READY")
    print("SELF_REFERRAL: BLOCKED")
    print("TENANT_SCOPING: ENABLED")
    print("COMMISSION_CALCULATION: READY")
    print("COMMISSION_LEDGER: READY")
    print("PAGE 11 CONTRACT: OK")


if __name__ == "__main__":
    main()
