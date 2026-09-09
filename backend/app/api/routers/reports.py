from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Order, Payment, Service, TenantUser

r = APIRouter(prefix="/reports", tags=["reports"])


async def _scope(tenant_id: int, claims: dict) -> None:
    if tenant_id <= 0:
        raise HTTPException(400, "invalid tenant")
    require_tenant_match(tenant_id, claims)


@r.get("/dashboard")
async def dashboard(
    tenant_id: int,
    claims=Depends(require_permission("reports.read")),
    db: AsyncSession = Depends(get_db),
):
    await _scope(tenant_id, claims)
    gross_sales = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.tenant_id == tenant_id, Order.status != "cancelled"))
    order_count = await db.scalar(select(func.count(Order.id)).where(Order.tenant_id == tenant_id))
    user_count = await db.scalar(select(func.count(TenantUser.user_id)).where(TenantUser.tenant_id == tenant_id))
    paid_revenue = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.tenant_id == tenant_id, Payment.status == "paid"))
    pending_payments = await db.scalar(select(func.count(Payment.id)).where(Payment.tenant_id == tenant_id, Payment.status.in_(["created", "awaiting_payment", "submitted", "verifying"])))
    service_count = await db.scalar(select(func.count(Service.id)).where(Service.tenant_id == tenant_id))
    active_services = await db.scalar(select(func.count(Service.id)).where(Service.tenant_id == tenant_id, Service.status == "active"))
    return {
        "tenant_id": tenant_id,
        "sales": str(gross_sales or 0),
        "orders": int(order_count or 0),
        "users": int(user_count or 0),
        "revenue": str(paid_revenue or 0),
        "pending_payments": int(pending_payments or 0),
        "services": {"total": int(service_count or 0), "active": int(active_services or 0)},
    }


@r.get("/sales")
async def sales(
    tenant_id: int,
    claims=Depends(require_permission("reports.read")),
    db: AsyncSession = Depends(get_db),
):
    await _scope(tenant_id, claims)
    total = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.tenant_id == tenant_id, Order.status != "cancelled"))
    return {"tenant_id": tenant_id, "gross_sales": str(total or 0)}
