from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.api.schemas import OrderCreate
from app.core.db import get_db
from app.models.entities import Order, OrderItem
from app.services.shop import create_order_from_plan

r = APIRouter(prefix="/orders", tags=["orders"])


def _is_admin_scope(claims: dict) -> bool:
    permissions = set(claims.get("permissions", []))
    return bool(claims.get("is_platform_owner")) or "orders.read" in permissions


@r.post("")
async def create(
    x: OrderCreate,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    permissions = claims.get("permissions", [])
    if "orders.write" not in permissions and "auth.telegram" not in permissions:
        raise HTTPException(403, "forbidden")
    require_tenant_match(tenant_id, claims)
    user_id = claims.get("user_id") or claims.get("sub")
    if not user_id:
        raise HTTPException(401, "user identity required")

    try:
        order = await create_order_from_plan(
            db=db,
            tenant_id=tenant_id,
            user_id=int(user_id),
            plan_id=x.plan_id,
            key=x.idempotency_key,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None

    return {"id": order.id, "total": str(order.total), "status": order.status}


@r.get("")
async def list_orders(
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    require_tenant_match(tenant_id, claims)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = (
        select(Order)
        .where(Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if not _is_admin_scope(claims):
        user_id = claims.get("user_id") or claims.get("sub")
        if not user_id:
            raise HTTPException(401, "user identity required")
        query = query.where(Order.user_id == int(user_id))
    result = await db.execute(query)
    return [
        {
            "id": order.id,
            "user_id": order.user_id,
            "status": order.status,
            "total": str(order.total),
            "created_at": order.created_at,
        }
        for order in result.scalars().all()
    ]


@r.get("/{order_id}")
async def read_order(
    order_id: int,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    order = await db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.tenant_id == tenant_id,
        )
    )
    if not order:
        raise HTTPException(404, "order_not_found")

    if not _is_admin_scope(claims):
        user_id = claims.get("user_id") or claims.get("sub")
        if not user_id or order.user_id != int(user_id):
            raise HTTPException(403, "forbidden")

    result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    items = result.scalars().all()
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total": str(order.total),
        "created_at": order.created_at,
        "items": [
            {
                "id": item.id,
                "plan_id": item.plan_id,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "product_name": item.snapshot_product_name,
                "plan_name": item.snapshot_plan_name,
                "price": str(item.snapshot_price) if item.snapshot_price is not None else None,
                "duration_days": item.snapshot_duration_days,
                "quota_gb": item.snapshot_quota_gb,
                "category": item.snapshot_category,
            }
            for item in items
        ],
    }
