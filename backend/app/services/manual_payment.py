from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Order, Payment, TenantSettings, User
from app.services.audit import audit_sensitive
from app.services.payments import transition


async def get_tenant_owner_telegram_id(db: AsyncSession, tenant_id: int) -> int:
    settings = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    value = (settings.settings or {}).get("owner_telegram_id") if settings else None
    try:
        owner_id = int(value)
    except (TypeError, ValueError):
        raise ValueError("tenant_owner_not_configured") from None
    if owner_id <= 0:
        raise ValueError("tenant_owner_not_configured")
    return owner_id


async def get_pending_manual_payment_for_user(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
) -> Payment | None:
    return await db.scalar(
        select(Payment)
        .join(Order, Order.id == Payment.order_id)
        .where(
            Payment.tenant_id == tenant_id,
            Payment.provider == "manual",
            Payment.status == "awaiting_payment",
            Order.tenant_id == tenant_id,
            Order.user_id == user_id,
        )
        .order_by(Payment.id.desc())
    )


async def submit_manual_receipt(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    receipt_reference: str,
) -> Payment:
    reference = (receipt_reference or "").strip()
    if not reference or len(reference) > 150:
        raise ValueError("invalid_receipt_reference")

    payment = await get_pending_manual_payment_for_user(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if not payment:
        raise ValueError("pending_manual_payment_not_found")

    transition(payment, "submitted")
    payment.reference = reference
    await db.flush()
    return payment


async def verify_manual_payment(
    db: AsyncSession,
    *,
    tenant_id: int,
    payment_id: int,
    actor_telegram_id: int,
    approve: bool,
) -> Payment:
    owner_id = await get_tenant_owner_telegram_id(db, tenant_id)
    if int(actor_telegram_id) != owner_id:
        raise PermissionError("tenant_owner_required")

    payment = await db.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
            Payment.provider == "manual",
        )
    )
    if not payment:
        raise ValueError("payment_not_found")

    if payment.status in {"paid", "rejected"}:
        return payment

    if payment.status != "submitted":
        raise ValueError("payment_not_ready_for_review")

    transition(payment, "paid" if approve else "rejected")
    audit_sensitive(
        db,
        action="payment.verify" if approve else "payment.reject",
        tenant_id=tenant_id,
        actor_type="telegram_owner",
        actor_id=owner_id,
        target_type="payment",
        target_id=payment.id,
        metadata={"approved": approve, "order_id": payment.order_id},
    )
    await db.flush()
    return payment


async def payment_customer(
    db: AsyncSession,
    *,
    tenant_id: int,
    payment_id: int,
) -> User | None:
    return await db.scalar(
        select(User)
        .join(Order, Order.user_id == User.id)
        .join(Payment, Payment.order_id == Order.id)
        .where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
        )
    )
