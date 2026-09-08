from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Payment
from app.payments_contract import PaymentStatus, validate_transition

VALID = {x.value for x in PaymentStatus}


def money(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("invalid amount") from None

    if result <= 0:
        raise ValueError("amount must be greater than zero")

    return result.quantize(Decimal("0.01"))


async def create_payment(
    db: AsyncSession,
    tenant_id: int,
    order_id: int,
    amount,
    provider: str,
    key: str,
) -> Payment:
    if not tenant_id:
        raise ValueError("tenant_id is required")

    if not order_id:
        raise ValueError("order_id is required")

    if not key or len(key) > 100:
        raise ValueError("invalid idempotency key")

    provider = (provider or "manual").strip().lower()

    if provider not in {"manual", "wallet", "zarinpal", "idpay", "nextpay"}:
        raise ValueError("unsupported payment provider")

    amount = money(amount)

    old = await db.scalar(
        select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.idempotency_key == key,
        )
    )

    if old:
        if Decimal(str(old.amount)) != amount:
            raise ValueError("idempotency key reused with different amount")
        if old.order_id != order_id:
            raise ValueError("idempotency key reused with different order")
        return old

    payment = Payment(
        tenant_id=tenant_id,
        order_id=order_id,
        amount=amount,
        provider=provider,
        status=PaymentStatus.CREATED.value,
        idempotency_key=key,
    )

    db.add(payment)
    await db.flush()

    return payment


def transition(payment: Payment, status: str) -> Payment:
    current = payment.status
    validate_transition(current, status)
    payment.status = status
    return payment


async def get_payment(
    db: AsyncSession,
    tenant_id: int,
    payment_id: int,
) -> Payment | None:
    return await db.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
        )
    )
