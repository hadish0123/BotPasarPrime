from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Order, Payment, User
from app.services.manual_payment import get_manual_card_details, get_tenant_owner_telegram_id
from app.services.payments import create_payment, transition
from app.services.wallet import post_wallet_transaction

MIN_TOPUP_TOMAN = Decimal("10000")
MAX_TOPUP_TOMAN = Decimal("10000000")


def validate_topup_amount(value: str | int | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except Exception as exc:
        raise ValueError("invalid_wallet_topup_amount") from exc
    if amount != amount.to_integral_value():
        raise ValueError("wallet_topup_amount_must_be_integer")
    if amount < MIN_TOPUP_TOMAN or amount > MAX_TOPUP_TOMAN:
        raise ValueError("wallet_topup_amount_out_of_range")
    return amount.quantize(Decimal("1"))


async def create_wallet_topup_payment(
    db: AsyncSession,
    *,
    tenant_id: int,
    user: User,
    amount: str | int | Decimal,
) -> tuple[Order, Payment, str, str]:
    topup_amount = validate_topup_amount(amount)
    card_number, card_holder = await get_manual_card_details(db)

    idempotency_key = f"wallet-topup:{tenant_id}:{user.id}:{uuid4().hex}"
    order = Order(
        tenant_id=tenant_id,
        user_id=user.id,
        status="created",
        total=topup_amount,
        idempotency_key=idempotency_key,
    )
    db.add(order)
    await db.flush()

    payment = await create_payment(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        amount=topup_amount,
        provider="wallet_topup_manual",
        key=idempotency_key,
    )
    if payment.status == "created":
        transition(payment, "awaiting_payment")
    await db.flush()
    return order, payment, card_number, card_holder


async def credit_verified_wallet_topup(
    db: AsyncSession,
    *,
    tenant_id: int,
    payment_id: int,
) -> Decimal:
    payment = await db.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
            Payment.provider == "wallet_topup_manual",
        )
    )
    if not payment or payment.status != "paid":
        raise ValueError("wallet_topup_payment_not_paid")

    order = await db.scalar(
        select(Order).where(
            Order.id == payment.order_id,
            Order.tenant_id == tenant_id,
        )
    )
    if not order:
        raise ValueError("wallet_topup_order_not_found")

    amount = validate_topup_amount(order.total)
    user = await db.scalar(select(User).where(User.id == order.user_id))
    if not user:
        raise ValueError("wallet_topup_user_not_found")

    await post_wallet_transaction(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        amount=amount,
        direction="credit",
        reason=f"wallet_topup:{order.id}",
        idempotency_key=f"wallet-topup-credit:{tenant_id}:{payment.id}",
    )
    order.status = "completed"
    await db.flush()
    return amount


async def wallet_topup_customer(
    db: AsyncSession,
    *,
    tenant_id: int,
    payment_id: int,
) -> User | None:
    payment = await db.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
            Payment.provider == "wallet_topup_manual",
        )
    )
    if not payment:
        return None
    return await db.scalar(select(User).where(User.id == select(Order.user_id).where(Order.id == payment.order_id).scalar_subquery()))


async def wallet_topup_owner(db: AsyncSession, tenant_id: int) -> int:
    return await get_tenant_owner_telegram_id(db, tenant_id)
