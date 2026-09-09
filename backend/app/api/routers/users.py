from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import TenantUser, User

r = APIRouter(prefix="/users", tags=["users"])


@r.get("")
async def users(
    tenant_id: int,
    claims=Depends(require_permission("users.read")),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    require_tenant_match(tenant_id, claims)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    current_user = int(claims.get("user_id") or claims.get("sub"))
    is_customer = claims.get("role") in {None, "customer"}

    query = (
        select(User, TenantUser)
        .join(TenantUser, TenantUser.user_id == User.id)
        .where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.status == "active",
        )
        .order_by(User.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if is_customer and not claims.get("is_platform_owner"):
        query = query.where(User.id == current_user)

    result = await db.execute(query)
    return [
        {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "role": membership.role,
            "status": membership.status,
            "created_at": user.created_at,
        }
        for user, membership in result.all()
    ]


@r.get("/{user_id}")
async def user_detail(
    user_id: int,
    tenant_id: int,
    claims=Depends(require_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    current_user = int(claims.get("user_id") or claims.get("sub"))
    if claims.get("role") in {None, "customer"} and not claims.get("is_platform_owner"):
        if user_id != current_user:
            raise HTTPException(403, "forbidden")

    result = await db.execute(
        select(User, TenantUser)
        .join(TenantUser, TenantUser.user_id == User.id)
        .where(
            User.id == user_id,
            TenantUser.tenant_id == tenant_id,
            TenantUser.status == "active",
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "user_not_found")
    user, membership = row
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "role": membership.role,
        "status": membership.status,
        "created_at": user.created_at,
    }
