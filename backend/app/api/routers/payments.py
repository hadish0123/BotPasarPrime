from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.api.schemas import PaymentCreate
from app.core.db import get_db
from app.models.entities import Order, OrderItem, Payment
from app.services.audit import audit_sensitive
from app.services.payments import create_payment, get_payment, transition
from app.services.provisioning import provision_service_for_order
from app.services.referrals import award_commission_for_order
from app.services.wallet import post_wallet_transaction

r = APIRouter(prefix="/payments", tags=["payments"])


async def _provision_paid_order(db: AsyncSession, tenant_id: int, order: Order):
    item = await db.scalar(
        select(OrderItem)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.id)
    )
    if item is None:
        raise ValueError("order_item_missing")
    service = await provision_service_for_order(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        user_id=order.user_id,
        plan_id=item.plan_id,
        duration_days=item.snapshot_duration_days,
        quota_gb=item.snapshot_quota_gb,
    )
    await db.commit()
    return service


@r.get("")
async def list_payments(
    tenant_id: int,
    claims=Depends(require_permission("payments.read")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    result = await db.execute(
        select(Payment)
        .where(Payment.tenant_id == tenant_id)
        .order_by(Payment.id.desc())
        .limit(100)
    )
    return [
        {
            "id": p.id,
            "order_id": p.order_id,
            "amount": str(p.amount),
            "provider": p.provider,
            "status": p.status,
            "reference": p.reference,
            "created_at": p.created_at,
        }
        for p in result.scalars().all()
    ]


@r.post("")
async def create(
    x: PaymentCreate,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    user_id = claims.get("user_id") or claims.get("sub")
    if not user_id:
        raise HTTPException(401, "user_identity_required")
    order = await db.scalar(
        select(Order).where(
            Order.id == x.order_id,
            Order.tenant_id == tenant_id,
            Order.user_id == int(user_id),
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
        if x.provider == "wallet" and payment.status in {"created", "awaiting_payment"}:
            await post_wallet_transaction(
                db,
                tenant_id=tenant_id,
                user_id=int(user_id),
                amount=x.amount,
                direction="debit",
                reason=f"order:{order.id}",
                idempotency_key=f"wallet-payment:{payment.id}",
            )
            transition(payment, "awaiting_payment")
            transition(payment, "submitted")
            transition(payment, "verifying")
            transition(payment, "paid")
            order.status = "paid"
            audit_sensitive(
                db,
                action="payment.wallet",
                tenant_id=tenant_id,
                actor_type="user",
                actor_id=user_id,
                target_type="payment",
                target_id=payment.id,
                metadata={"order_id": order.id, "amount": str(payment.amount)},
            )
        elif payment.status == "created":
            transition(payment, "awaiting_payment")
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    service = None
    if x.provider == "wallet" and payment.status == "paid":
        try:
            await award_commission_for_order(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                referred_user_id=order.user_id,
                order_amount=order.total,
            )
        except ValueError:
            pass
        service = await _provision_paid_order(db, tenant_id, order)
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "status": payment.status,
        "provider": payment.provider,
        "service_id": service.id if service else None,
    }


@r.get("/{payment_id}")
async def read_payment(
    payment_id: int,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    payment = await get_payment(db=db, tenant_id=tenant_id, payment_id=payment_id)
    if not payment:
        raise HTTPException(404, "payment_not_found")
    order = await db.get(Order, payment.order_id)
    user_id = claims.get("user_id") or claims.get("sub")
    if not claims.get("is_platform_owner") and (
        not order or not user_id or order.user_id != int(user_id)
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
    payment = await get_payment(db=db, tenant_id=tenant_id, payment_id=payment_id)
    if not payment:
        raise HTTPException(404, "payment_not_found")
    order = await db.get(Order, payment.order_id)
    user_id = claims.get("user_id") or claims.get("sub")
    if not order or not user_id or order.user_id != int(user_id):
        raise HTTPException(403, "forbidden")
    if not reference or len(reference.strip()) > 150:
        raise HTTPException(400, "invalid_reference")
    try:
        transition(payment, "submitted")
        payment.reference = reference.strip()
        await db.commit()
        return {"id": payment.id, "status": payment.status}
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from None


@r.post("/{payment_id}/verify")
async def verify_payment(
    payment_id: int,
    tenant_id: int,
    approve: bool = True,
    claims=Depends(require_permission("payments.verify")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    payment = await get_payment(db=db, tenant_id=tenant_id, payment_id=payment_id)
    if not payment:
        raise HTTPException(404, "payment_not_found")
    order = await db.get(Order, payment.order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(404, "order_not_found")
    try:
        if approve:
            transition(payment, "verifying")
            transition(payment, "paid")
            order.status = "paid"
            action = "payment.verify"
        else:
            transition(payment, "rejected")
            action = "payment.reject"
        audit_sensitive(
            db,
            action=action,
            tenant_id=tenant_id,
            actor_type="admin",
            actor_id=claims.get("user_id") or claims.get("sub"),
            target_type="payment",
            target_id=payment.id,
            metadata={"order_id": order.id, "status": payment.status},
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from None
    service = None
    if approve:
        try:
            await award_commission_for_order(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                referred_user_id=order.user_id,
                order_amount=order.total,
            )
        except ValueError:
            pass
        try:
            service = await _provision_paid_order(db, tenant_id, order)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(502, f"provisioning_failed:{exc}") from None
    return {
        "id": payment.id,
        "order_id": order.id,
        "status": payment.status,
        "service_id": service.id if service else None,
        "service_status": service.status if service else None,
    }


@r.post("/{payment_id}/expire")
async def expire_payment(
    payment_id: int,
    tenant_id: int,
    claims=Depends(require_permission("payments.verify")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    payment = await get_payment(db=db, tenant_id=tenant_id, payment_id=payment_id)
    if not payment:
        raise HTTPException(404, "payment_not_found")
    try:
        transition(payment, "expired")
        audit_sensitive(
            db,
            action="payment.expire",
            tenant_id=tenant_id,
            actor_type="admin",
            actor_id=claims.get("user_id") or claims.get("sub"),
            target_type="payment",
            target_id=payment.id,
            metadata={"order_id": payment.order_id},
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from None
    return {"id": payment.id, "status": payment.status}


@r.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: int,
    tenant_id: int,
    claims=Depends(require_permission("payments.refund")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    payment = await get_payment(db=db, tenant_id=tenant_id, payment_id=payment_id)
    if not payment:
        raise HTTPException(404, "payment_not_found")
    order = await db.get(Order, payment.order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(404, "order_not_found")
    try:
        transition(payment, "refunded")
        order.status = "refunded"
        if payment.provider == "wallet":
            await post_wallet_transaction(
                db,
                tenant_id=tenant_id,
                user_id=order.user_id,
                amount=payment.amount,
                direction="credit",
                reason=f"refund:{order.id}",
                idempotency_key=f"wallet-refund:{payment.id}",
            )
        audit_sensitive(
            db,
            action="payment.refund",
            tenant_id=tenant_id,
            actor_type="admin",
            actor_id=claims.get("user_id") or claims.get("sub"),
            target_type="payment",
            target_id=payment.id,
            metadata={"order_id": order.id, "amount": str(payment.amount)},
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc)) from None
    return {"id": payment.id, "order_id": order.id, "status": payment.status}
