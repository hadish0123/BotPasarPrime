from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.db import get_db
from app.models.entities import Order, Payment, Tenant, TenantUser, User

r = APIRouter(prefix="/admin", tags=["admin"])


@r.get("/dashboard")
async def dashboard(
    claims=Depends(require_permission("dashboard.read")),
    db: AsyncSession = Depends(get_db),
):
    owner = bool(claims.get("is_platform_owner"))
    tenant_id = claims.get("tenant_id")

    if not owner and tenant_id is None:
        from fastapi import HTTPException
        raise HTTPException(403, "tenant_context_required")

    if owner:
        tenant_count_query = select(func.count(Tenant.id)).where(
            Tenant.is_deleted.is_(False)
        )
        user_query = select(func.count(func.distinct(User.id))).select_from(User)
        order_query = select(func.count(Order.id))
        payment_query = select(func.count(Payment.id)).where(
            Payment.status.in_(["created", "awaiting_payment", "submitted", "verifying"])
        )
    else:
        tenant_id = int(tenant_id)
        tenant_count_query = select(func.count(Tenant.id)).where(
            Tenant.id == tenant_id,
            Tenant.is_deleted.is_(False),
        )
        user_query = (
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .join(TenantUser, TenantUser.user_id == User.id)
            .where(TenantUser.tenant_id == tenant_id)
        )
        order_query = select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
        payment_query = select(func.count(Payment.id)).where(
            Payment.tenant_id == tenant_id,
            Payment.status.in_(["created", "awaiting_payment", "submitted", "verifying"]),
        )

    return {
        "tenants": (await db.scalar(tenant_count_query)) or 0,
        "users": (await db.scalar(user_query)) or 0,
        "orders": (await db.scalar(order_query)) or 0,
        "pending_payments": (await db.scalar(payment_query)) or 0,
    }
