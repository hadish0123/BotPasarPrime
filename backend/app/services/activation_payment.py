from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Order, OrderItem, Payment, Plan, Product
from app.services.payments import create_payment

ACTIVATION_PROVIDER = "manual"
ACTIVATION_IDEMPOTENCY_PREFIX = "tenant-activation"


async def create_activation_order(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
    tenant_idempotency_key: str,
):
    """
    Creates a real Order + OrderItem + Payment for personal Tenant activation.

    No payment is marked paid here.
    """

    if not tenant_id or not user_id:
        raise ValueError("tenant_id and user_id are required")

    fee = Decimal(str(settings.activation_fee_toman)).quantize(Decimal("0.01"))

    if fee <= 0:
        raise ValueError("activation fee must be positive")

    key = f"{ACTIVATION_IDEMPOTENCY_PREFIX}:{tenant_id_idempotency_key(tenant_idempotency_key)}"

    existing = await db.scalar(
        select(Order).where(
            Order.tenant_id == tenant_id,
            Order.idempotency_key == key,
        )
    )

    if existing:
        payment = await db.scalar(
            select(Payment).where(
                Payment.tenant_id == tenant_id,
                Payment.order_id == existing.id,
            )
        )
        return existing, payment

    # Dedicated internal activation product/plan.
    product = await db.scalar(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.name == "Personal Tenant Activation",
        )
    )

    if not product:
        product = Product(
            tenant_id=tenant_id,
            name="Personal Tenant Activation",
            description="One-time activation fee for personal PasarGuard Tenant",
            active=True,
            category="activation",
        )
        db.add(product)
        await db.flush()

    plan = await db.scalar(
        select(Plan).where(
            Plan.product_id == product.id,
            Plan.name == "Activation",
        )
    )

    if not plan:
        plan = Plan(
            product_id=product.id,
            name="Activation",
            price=fee,
            duration_days=0,
            quota_gb=None,
            active=True,
        )
        db.add(plan)
        await db.flush()

    order = Order(
        tenant_id=tenant_id,
        user_id=user_id,
        status="awaiting_payment",
        total=fee,
        idempotency_key=key,
    )

    db.add(order)
    await db.flush()

    db.add(
        OrderItem(
            order_id=order.id,
            plan_id=plan.id,
            quantity=1,
            unit_price=fee,
        )
    )

    await db.flush()

    payment = await create_payment(
        db=db,
        tenant_id=tenant_id,
        order_id=order.id,
        amount=fee,
        provider=ACTIVATION_PROVIDER,
        key=f"{key}:payment",
    )

    payment.status = "awaiting_payment"

    await db.flush()

    return order, payment


def tenant_id_idempotency_key(value: str) -> str:
    value = (value or "").strip()

    if not value:
        raise ValueError("activation idempotency key is required")

    # Never put secrets in this key.
    if len(value) > 70:
        value = value[:70]

    return value.replace(":", "_").replace(" ", "_")
