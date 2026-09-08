from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.entities import Order, Payment, Tenant, User

r = APIRouter(prefix="/admin", tags=["admin"])


@r.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    return {
        "tenants": await db.scalar(select(func.count(Tenant.id))),
        "users": await db.scalar(select(func.count(User.id))),
        "orders": await db.scalar(select(func.count(Order.id))),
        "pending_payments": await db.scalar(
            select(func.count(Payment.id)).where(
                Payment.status.in_(["created", "submitted", "verifying"])
            )
        ),
    }
