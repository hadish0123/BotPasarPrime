from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manual_card_purchase_flow_contract():
    tenant = (ROOT / "app/bot/tenant.py").read_text()
    service = (ROOT / "app/services/manual_payment.py").read_text()
    purchase = (ROOT / "app/services/purchase.py").read_text()
    config = (ROOT / "app/core/config.py").read_text()

    required_tenant_markers = [
        "خرید کانفیگ",
        "purchase:direct:",
        "get_manual_card_details",
        "filters.PHOTO",
        "payment:approve:",
        "payment:reject:",
        "fulfill_verified_payment",
        "لینک اشتراک",
    ]
    for marker in required_tenant_markers:
        assert marker in tenant

    required_service_markers = [
        "get_manual_card_details",
        "submit_manual_receipt",
        "verify_manual_payment",
        "tenant_owner_required",
        "awaiting_payment",
        "submitted",
        "paid",
        "rejected",
    ]
    for marker in required_service_markers:
        assert marker in service

    assert 'provider="manual"' in purchase
    assert "fulfill_verified_payment" in purchase
    assert "manual_payment_card_number" in config
    assert "manual_payment_card_holder" in config
