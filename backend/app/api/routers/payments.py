from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import PaymentCreate
from app.core.db import get_db
from app.models.entities import Order
from app.services.payments import create_payment, get_payment

r = APIRouter(prefix="/payments", tags=["payments"])


@r.post("")
async def create(
    x: PaymentCreate,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(Order).where(
            Order.id == x.order_id,
            Order.tenant_id == tenant_id,
        )
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="order_not_found",
        )

    if order.status in {"paid", "completed", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail="order_not_payable",
        )

    try:
        payment = await create_payment(
            db=db,
            tenant_id=tenant_id,
            order_id=x.order_id,
            amount=x.amount,
            provider=x.provider,
            key=x.idempotency_key,
        )

        if payment.status == "created":
            payment.status = "awaiting_payment"

        await db.commit()

        return {
            "id": payment.id,
            "order_id": payment.order_id,
            "status": payment.status,
            "provider": payment.provider,
        }

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None


@r.get("/{payment_id}")
async def read_payment(
    payment_id: int,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    payment = await get_payment(
        db=db,
        tenant_id=tenant_id,
        payment_id=payment_id,
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="payment_not_found",
        )

    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "amount": str(payment.amount),
        "provider": payment.provider,
        "status": payment.status,
        "reference": payment.reference,
    }


@r.post("/{payment_id}/submit")
async def submit_payment(
    payment_id: int,
    tenant_id: int,
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    payment = await get_payment(
        db=db,
        tenant_id=tenant_id,
        payment_id=payment_id,
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="payment_not_found",
        )

    if not reference or len(reference.strip()) > 150:
        raise HTTPException(
            status_code=400,
            detail="invalid_reference",
        )

    try:
        from app.services.payments import transition

        transition(payment, "submitted")
        payment.reference = reference.strip()

        await db.commit()

        return {
            "id": payment.id,
            "status": payment.status,
        }

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None


# IMPORTANT:
# There is intentionally NO public endpoint here that allows
# arbitrary users to set a payment to "paid".
#
# Paid/rejected/verifying transitions will be connected to the
# authenticated owner/admin/payment workflow in the later RBAC
# stages. This prevents financial privilege escalation.
