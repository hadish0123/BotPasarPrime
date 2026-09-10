from pathlib import Path

from app.services import wallet_topup
from app.bot import tenant

ROOT = Path(__file__).resolve().parents[1]


def test_wallet_topup_contract():
    source = (ROOT / "app" / "bot" / "tenant.py").read_text(encoding="utf-8")
    assert "💰 کیف پول" in source
    assert "wallet:topup" in source
    assert "wallet_topup_waiting" in source
    assert "filters.PHOTO" in source
    assert "credit_verified_wallet_topup" in source
    assert "wallet_topup_manual" in source
    assert hasattr(wallet_topup, "validate_topup_amount")
    assert hasattr(wallet_topup, "create_wallet_topup_payment")
    assert hasattr(wallet_topup, "submit_wallet_topup_receipt")
    assert hasattr(wallet_topup, "credit_verified_wallet_topup")


def test_wallet_topup_limits():
    assert wallet_topup.validate_topup_amount("10000") == 10000
    assert wallet_topup.validate_topup_amount("10000000") == 10000000
    for value in ("9999", "10000001", "abc"):
        try:
            wallet_topup.validate_topup_amount(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid top-up amount was accepted")


def test_tenant_bot_registers_wallet_handlers():
    app = tenant.build_tenant_application(token="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", tenant_id=1, bot_instance_id=1)
    patterns = [getattr(h, "callback", None) for h in app.handlers.get(0, [])]
    assert patterns
