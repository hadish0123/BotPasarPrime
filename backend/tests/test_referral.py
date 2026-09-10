from decimal import Decimal

import pytest

from app.wallet_coupon_referral_contract import calculate_commission, validate_referral


def test_self_referral_is_rejected():
    with pytest.raises(ValueError, match="self referral"):
        validate_referral(7, 7)


def test_cross_user_referral_is_allowed():
    validate_referral(7, 8)


def test_commission_is_money_quantized():
    assert calculate_commission("1250.00", "7.5") == Decimal("93.75")


def test_commission_percentage_is_bounded():
    with pytest.raises(ValueError, match="invalid commission"):
        calculate_commission("100", "100.01")
