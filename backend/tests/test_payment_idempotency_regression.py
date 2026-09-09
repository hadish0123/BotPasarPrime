from decimal import Decimal

from app.payments_contract import PaymentStatus, validate_transition


def test_payment_state_machine_allows_submission_and_verification():
    validate_transition(PaymentStatus.CREATED.value, PaymentStatus.AWAITING_PAYMENT.value)
    validate_transition(PaymentStatus.AWAITING_PAYMENT.value, PaymentStatus.SUBMITTED.value)
    validate_transition(PaymentStatus.SUBMITTED.value, PaymentStatus.VERIFYING.value)
    validate_transition(PaymentStatus.VERIFYING.value, PaymentStatus.PAID.value)


def test_paid_payment_cannot_be_reopened():
    try:
        validate_transition(PaymentStatus.PAID.value, PaymentStatus.AWAITING_PAYMENT.value)
    except ValueError:
        return
    raise AssertionError("paid payment must be terminal")


def test_financial_decimal_is_exact():
    assert Decimal("100.10") + Decimal("0.20") == Decimal("100.30")
