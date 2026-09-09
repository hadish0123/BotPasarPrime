from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.db import get_db
from app.models.entities import Order, Payment, Tenant, User

r = APIRouter(prefix="/admin", tags=["admin"])


@r.get("/dashboard")
async def dashboard(claims=Depends(require_permission("dashboard.read")), db: AsyncSession = Depends(get_db)):
    owner = bool(claims.get("is_platform_owner"))
    tenant_id = claims.get("tenant_id")
    tenant_filter = lambda column: column if owner else column == int(tenant_id)

    tenant_count = await db.scalar(select(func.count(Tenant.id)).where(Tenant.is_deleted.is_(False))) if owner else await db.scalar(select(func.count(Tenant.id)).where(Tenant.id == int(tenant_id), Tenant.is_deleted.is_(False)))
    order_query = select(func.count(Order.id))
    payment_query = select(func.count(Payment.id)).where(Payment.status.in_(["created", "awaiting_payment", "submitted", "verifying"]))
    user_query = select(func.count(func.distinct(User.id))).select_from(User)
    if not owner:
        from app.models.entities import TenantUser
        user_query = user_query.join(TenantUser, TenantUser.user_id == User.id).where(TenantUser.tenant_id == int(tenant_id))
        order_query = order_query.where(Order.tenant_id == int(tenant_id))
        payment_query = payment_query.where(Payment.tenant_id == int(tenant_id))

    return {
        "tenants": tenant_count or 0,
        "users": (await db.scalar(user_query)) or 0,
        "orders": (await db.scalar(order_query)) or 0,
        "pending_payments": (await db.scalar(payment_query)) or 0,
    }
