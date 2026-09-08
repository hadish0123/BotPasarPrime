from app.services.onboarding import activation_fee


def test_fee():
    assert activation_fee("personal_panel") == 250000
    assert activation_fee("primevpn_representative") == 0
