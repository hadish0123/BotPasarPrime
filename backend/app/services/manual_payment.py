from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Order, Payment, SystemSetting, TenantSettings, User
from app.services.audit import audit_sensitive
from app.services.payments import transition


async def get_tenant_owner_telegram_id(db: AsyncSession, tenant_id: int) -> int:
    tenant_settings = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    value = (tenant_settings.settings or {}).get("owner_telegram_id") if tenant_settings else None
    try:
        owner_id = int(value)
    except (TypeError, ValueError):
        owner_id = 0

    if owner_id > 0:
        return owner_id

    # Manual payment review must never get stuck merely because a Tenant
    # does not yet have an explicit owner_telegram_id. Fall back to the
    # platform administrator configured in the environment.
    platform_owner = settings.owner_telegram_id
    if platform_owner and int(platform_owner) > 0:
        return int(platform_owner)

    raise ValueError("tenant_owner_not_configured")


async def get_manual_card_details(db: AsyncSession) -> tuple[str, str]:
    number = settings.manual_payment_card_number.strip()
    holder = settings.manual_payment_card_holder.strip()

    if not number:
        setting = await db.scalar(
            select(SystemSetting).where(SystemSetting.key == "manual_payment_card_number")
        )
        if setting:
            number = str(setting.value or "").strip()

    if not holder:
        setting = await db.scalar(
            select(SystemSetting).where(SystemSetting.key == "manual_payment_card_holder")
        )
        if setting:
            holder = str(setting.value or "").strip()

    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) != 16:
        raise ValueError("manual_payment_card_not_configured")

    return digits, holder


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
            Payment.status.in_({"awaiting_payment", "submitted"}),
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

    if payment.status == "submitted":
        if payment.reference == reference:
            return payment
        raise ValueError("payment_receipt_already_submitted")

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
