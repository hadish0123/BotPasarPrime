from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.api.schemas import PaymentCreate
from app.core.db import get_db
from app.models.entities import Order
from app.services.payments import create_payment, get_payment

r = APIRouter(prefix="/payments", tags=["payments"])


@r.post("")
async def create(
    x: PaymentCreate,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    user_id = claims.get("user_id") or claims.get("sub")
    order = await db.scalar(
        select(Order).where(
            Order.id == x.order_id,
            Order.tenant_id == tenant_id,
            Order.user_id == int(user_id) if user_id else False,
        )
    )
    if not order:
        raise HTTPException(404, "order_not_found")
    if order.status in {"paid", "completed", "cancelled"}:
        raise HTTPException(409, "order_not_payable")
    if x.amount != order.total:
        raise HTTPException(400, "payment_amount_mismatch")

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
        raise HTTPException(400, str(exc)) from None


@r.get("/{payment_id}")
async def read_payment(
    payment_id: int,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    payment = await get_payment(
        db=db,
        tenant_id=tenant_id,
        payment_id=payment_id,
    )
    if not payment:
        raise HTTPException(404, "payment_not_found")
    order = await db.get(Order, payment.order_id)
    user_id = claims.get("user_id") or claims.get("sub")
    if not claims.get("is_platform_owner") and (
        not order or order.user_id != int(user_id)
    ):
        raise HTTPException(403, "forbidden")
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
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    payment = await get_payment(
        db=db,
        tenant_id=tenant_id,
        payment_id=payment_id,
    )
    if not payment:
        raise HTTPException(404, "payment_not_found")
    order = await db.get(Order, payment.order_id)
    user_id = claims.get("user_id") or claims.get("sub")
    if not claims.get("is_platform_owner") and (
        not order or order.user_id != int(user_id)
    ):
        raise HTTPException(403, "forbidden")
    if not reference or len(reference.strip()) > 150:
        raise HTTPException(400, "invalid_reference")
    try:
        from app.services.payments import transition

        transition(payment, "submitted")
        payment.reference = reference.strip()
        await db.commit()
        return {"id": payment.id, "status": payment.status}
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from None
