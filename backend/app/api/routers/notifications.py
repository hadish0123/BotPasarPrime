from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.core.db import get_db
from app.models.entities import Notification

r = APIRouter(prefix="/notifications", tags=["notifications"])


def _current_user(claims: dict) -> int:
    value = claims.get("user_id") or claims.get("sub")
    if value is None:
        raise HTTPException(401, "user identity required")
    return int(value)


@r.get("")
async def notifications(
    tenant_id: int,
    unread_only: bool = False,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    user_id = _current_user(claims)
    query = (
        select(Notification)
        .where(Notification.tenant_id == tenant_id, Notification.user_id == user_id)
        .order_by(Notification.id.desc())
        .limit(100)
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    rows = (await db.scalars(query)).all()
    return [
        {"id": row.id, "kind": row.kind, "title": row.title, "body": row.body,
         "sent_at": row.sent_at, "read_at": row.read_at, "is_read": row.read_at is not None}
        for row in rows
    ]


@r.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    user_id = _current_user(claims)
    row = await db.scalar(select(Notification).where(
        Notification.id == notification_id,
        Notification.tenant_id == tenant_id,
        Notification.user_id == user_id,
    ))
    if row is None:
        raise HTTPException(404, "notification_not_found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await db.commit()
    return {"id": row.id, "is_read": True, "read_at": row.read_at}


@r.post("/read-all")
async def mark_all_read(
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    user_id = _current_user(claims)
    rows = (await db.scalars(select(Notification).where(
        Notification.tenant_id == tenant_id,
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    ))).all()
    timestamp = datetime.now(UTC)
    for row in rows:
        row.read_at = timestamp
    await db.commit()
    return {"updated": len(rows)}
