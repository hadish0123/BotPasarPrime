from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import OrderCreate
from app.core.db import get_db
from app.services.shop import create_order_from_plan

r = APIRouter(prefix="/orders", tags=["orders"])


@r.post("")
async def create(
    x: OrderCreate,
    tenant_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await create_order_from_plan(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            plan_id=x.plan_id,
            key=x.idempotency_key,
        )

        await db.commit()

        return {
            "id": order.id,
            "total": str(order.total),
            "status": order.status,
        }

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None
