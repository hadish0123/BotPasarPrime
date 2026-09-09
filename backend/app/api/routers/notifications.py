from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.core.db import get_db
from app.models.entities import Notification

r = APIRouter(prefix="/notifications", tags=["notifications"])


@r.get("")
async def notifications(
    tenant_id: int,
    user_id: int | None = None,
    unread_only: bool = False,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    current_user = claims.get("user_id") or claims.get("sub")
    if current_user is None:
        raise HTTPException(401, "user identity required")
    requested_user = int(user_id) if user_id is not None else int(current_user)
    if requested_user != int(current_user) and not claims.get("is_platform_owner"):
        raise HTTPException(403, "forbidden")

    query = (
        select(Notification)
        .where(Notification.tenant_id == tenant_id, Notification.user_id == requested_user)
        .order_by(Notification.id.desc())
        .limit(100)
    )
    if unread_only:
        query = query.where(Notification.sent_at.is_(None))

    rows = (await db.scalars(query)).all()
    return [
        {"id": row.id, "kind": row.kind, "title": row.title, "body": row.body, "sent_at": row.sent_at}
        for row in rows
    ]
