from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Payment
from app.payments_contract import PaymentStatus, validate_transition

VALID = {x.value for x in PaymentStatus}


class PaymentGatewayError(RuntimeError):
    """Raised when a configured external gateway cannot be contacted."""


class PaymentGateway:
    name = "base"

    async def create_checkout(self, *, payment: Payment, callback_url: str) -> str:
        raise PaymentGatewayError(f"gateway_not_configured:{self.name}")

    async def verify(self, *, payment: Payment) -> str:
        raise PaymentGatewayError(f"gateway_not_configured:{self.name}")

    async def refund(self, *, payment: Payment) -> str:
        raise PaymentGatewayError(f"gateway_not_configured:{self.name}")


class ZarinpalGateway(PaymentGateway):
    name = "zarinpal"


class IDPayGateway(PaymentGateway):
    name = "idpay"


class NextPayGateway(PaymentGateway):
    name = "nextpay"


GATEWAYS: dict[str, PaymentGateway] = {
    "zarinpal": ZarinpalGateway(),
    "idpay": IDPayGateway(),
    "nextpay": NextPayGateway(),
}


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
    if provider not in {"manual", "wallet", *GATEWAYS}:
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
        if old.order_id != order_id or old.provider != provider:
            raise ValueError("idempotency key reused with different payment")
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
    validate_transition(payment.status, status)
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
