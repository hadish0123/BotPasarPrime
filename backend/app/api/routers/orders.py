from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.api.schemas import OrderCreate
from app.core.db import get_db
from app.services.shop import create_order_from_plan

r = APIRouter(prefix="/orders", tags=["orders"])


@r.post("")
async def create(x: OrderCreate, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    if "orders.write" not in claims.get("permissions", []) and "auth.telegram" not in claims.get("permissions", []):
        raise HTTPException(403, "forbidden")
    require_tenant_match(tenant_id, claims)
    user_id = claims.get("user_id") or claims.get("sub")
    if not user_id:
        raise HTTPException(401, "user identity required")
    try:
        order = await create_order_from_plan(db=db, tenant_id=tenant_id, user_id=int(user_id), plan_id=x.plan_id, key=x.idempotency_key)
        await db.commit()
        return {"id": order.id, "total": str(order.total), "status": order.status}
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
