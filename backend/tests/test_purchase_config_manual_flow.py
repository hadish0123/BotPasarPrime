from pathlib import Path

from app.services import manual_payment, purchase
from app.bot import tenant


ROOT = Path(__file__).resolve().parents[1]


def test_manual_purchase_flow_contract():
    source = (ROOT / "app" / "bot" / "tenant.py").read_text(encoding="utf-8")

    assert "🛒 خرید کانفیگ" in source
    assert 'purchase:product:' in source
    assert 'purchase:plan:' in source
    assert 'purchase:wallet:' in source
    assert 'purchase:direct:' in source
    assert "filters.PHOTO" in source
    assert "payment:approve:" in source
    assert "payment:reject:" in source
    assert "fulfill_verified_payment" in source

    assert hasattr(tenant, "build_tenant_application")
    assert hasattr(manual_payment, "get_manual_card_details")
    assert hasattr(manual_payment, "submit_manual_receipt")
    assert hasattr(manual_payment, "verify_manual_payment")
    assert hasattr(purchase, "purchase_with_wallet")
    assert hasattr(purchase, "create_direct_payment")
    assert hasattr(purchase, "fulfill_verified_payment")


def test_pasarguard_purchase_provisioning_contract():
    source = (ROOT / "app" / "services" / "purchase.py").read_text(encoding="utf-8")

    assert "client.create_user" in source
    assert "client.get_subscription" in source
    assert "subscription_url" in source
    assert "Service(" in source
    assert 'status="active"' in source
    assert "_normalize_panel_base_url" in source
