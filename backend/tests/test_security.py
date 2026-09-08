from app.security.crypto import SecretBox
from app.security.rbac import allowed


def test_mask():
    assert SecretBox.mask("12345678") == "****5678"


def test_rbac():
    assert allowed("Finance", "payments.approve")
    assert not allowed("Viewer", "admins.write")
