from enum import StrEnum


class PaymentStatus(StrEnum):
    CREATED = "created"
    AWAITING_PAYMENT = "awaiting_payment"
    SUBMITTED = "submitted"
    VERIFYING = "verifying"
    PAID = "paid"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REFUNDED = "refunded"


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatus.CREATED: {
        PaymentStatus.AWAITING_PAYMENT,
        PaymentStatus.REJECTED,
        PaymentStatus.EXPIRED,
    },
    PaymentStatus.AWAITING_PAYMENT: {
        PaymentStatus.SUBMITTED,
        PaymentStatus.REJECTED,
        PaymentStatus.EXPIRED,
    },
    PaymentStatus.SUBMITTED: {
        PaymentStatus.VERIFYING,
        PaymentStatus.REJECTED,
        PaymentStatus.EXPIRED,
    },
    PaymentStatus.VERIFYING: {
        PaymentStatus.PAID,
        PaymentStatus.REJECTED,
        PaymentStatus.EXPIRED,
    },
    PaymentStatus.PAID: {
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.REJECTED: set(),
    PaymentStatus.EXPIRED: set(),
    PaymentStatus.REFUNDED: set(),
}


def validate_transition(current: str, target: str) -> None:
    if target not in {x.value for x in PaymentStatus}:
        raise ValueError("invalid payment status")

    if current == target:
        return

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"invalid payment transition: {current} -> {target}")


def payment_snapshot() -> dict:
    return {
        "statuses": [x.value for x in PaymentStatus],
        "transitions": {k: sorted(v) for k, v in ALLOWED_TRANSITIONS.items()},
        "manual_payment_supported": True,
        "wallet_supported": True,
        "real_gateway_adapter_supported": True,
        "mock_payment": False,
    }
