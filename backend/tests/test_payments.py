from app.services.payments import transition


class P:
    def __init__(self):
        self.status = "created"


def test_payment_transition_to_awaiting_payment():
    p = P()
    transition(p, "awaiting_payment")
    assert p.status == "awaiting_payment"


def test_payment_transition_to_submitted():
    p = P()
    transition(p, "awaiting_payment")
    transition(p, "submitted")
    assert p.status == "submitted"


def test_payment_transition_to_verifying():
    p = P()
    transition(p, "awaiting_payment")
    transition(p, "submitted")
    transition(p, "verifying")
    assert p.status == "verifying"


def test_payment_transition_to_paid():
    p = P()
    transition(p, "awaiting_payment")
    transition(p, "submitted")
    transition(p, "verifying")
    transition(p, "paid")
    assert p.status == "paid"


def test_invalid_direct_transition_is_rejected():
    p = P()

    try:
        transition(p, "paid")
    except ValueError as exc:
        assert "invalid payment transition" in str(exc)
    else:
        raise AssertionError("created -> paid must be rejected")
