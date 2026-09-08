from __future__ import annotations

from typing import Any

from app.architecture.contracts import (
    CrossTenantAccessError,
    MissingTenantContextError,
    TenantContext,
)

TENANT_SCOPED_ENTITIES = {
    "TenantSettings",
    "TenantBranding",
    "TenantCredential",
    "TenantUser",
    "Product",
    "Plan",
    "Order",
    "OrderItem",
    "Payment",
    "Wallet",
    "WalletTransaction",
    "Coupon",
    "CouponUsage",
    "Referral",
    "ReferralTransaction",
    "Service",
    "Ticket",
    "TicketMessage",
    "Notification",
    "Broadcast",
    "AuditLog",
    "BotInstance",
    "ApprovalRequest",
}


def assert_business_tenant_context(
    context: TenantContext | None,
) -> TenantContext:
    if context is None:
        raise MissingTenantContextError("Business operation requires Tenant Context")

    if context.tenant_id is None and not context.is_platform_owner:
        raise MissingTenantContextError("Tenant ID is required")

    return context


def assert_tenant_id(
    tenant_id: int,
    context: TenantContext | None,
) -> None:
    context = assert_business_tenant_context(context)

    if context.tenant_id == tenant_id:
        return

    if getattr(context, "is_platform_owner", False):
        return

    if context.tenant_id != tenant_id:
        raise CrossTenantAccessError("Cross-tenant access denied")


def assert_model_is_scoped(model: Any) -> None:
    name = getattr(model, "__name__", str(model))

    if name not in TENANT_SCOPED_ENTITIES:
        raise TypeError(f"{name} is not registered as tenant-scoped")


def validate_business_model(model: Any) -> None:
    assert_model_is_scoped(model)

    if not hasattr(model, "tenant_id"):
        raise TypeError(f"{model.__name__} must expose tenant_id")


__all__ = [
    "TENANT_SCOPED_ENTITIES",
    "assert_business_tenant_context",
    "assert_tenant_id",
    "assert_model_is_scoped",
    "validate_business_model",
]
