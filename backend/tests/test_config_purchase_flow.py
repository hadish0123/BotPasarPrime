from app.bot.tenant import TenantBotSection, build_tenant_application
from app.services import purchase


def test_purchase_module_and_button_contract():
    assert TenantBotSection.PURCHASE.value == "tenant:purchase"
    assert callable(purchase.purchase_with_wallet)
    assert callable(purchase.create_direct_payment)
    assert callable(purchase.fulfill_verified_payment)


def test_tenant_bot_registers_purchase_handlers():
    app = build_tenant_application(token="123456:AAAAAAAAAAAAAAAAAAAA", tenant_id=1, bot_instance_id=1)
    callback_patterns = []
    for handler in app.handlers.get(0, []):
        callback_patterns.append(type(handler).__name__)
    assert "CallbackQueryHandler" in callback_patterns
    assert "MessageHandler" in callback_patterns
