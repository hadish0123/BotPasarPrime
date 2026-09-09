from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.api.schemas import TicketCreate
from app.core.db import get_db
from app.models.entities import Ticket, TicketMessage

r = APIRouter(prefix="/support", tags=["support"])


@r.post("/tickets")
async def create(
    x: TicketCreate,
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    user_id = claims.get("user_id") or claims.get("sub")
    if not user_id:
        raise HTTPException(401, "user identity required")
    t = Ticket(tenant_id=tenant_id, user_id=int(user_id), subject=x.subject)
    db.add(t)
    await db.flush()
    db.add(TicketMessage(ticket_id=t.id, sender_type="user", body=x.body))
    await db.commit()
    return {"id": t.id, "status": t.status}


@r.get("/tickets")
async def list_tickets(
    tenant_id: int,
    claims=Depends(require_permission("tickets.read")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    query = select(Ticket).where(Ticket.tenant_id == tenant_id).order_by(Ticket.id.desc()).limit(100)
    if claims.get("role") in {None, "customer"} and not claims.get("is_platform_owner"):
        user_id = claims.get("user_id") or claims.get("sub")
        query = query.where(Ticket.user_id == int(user_id))
    rows = (await db.scalars(query)).all()
    return [{"id": t.id, "user_id": t.user_id, "subject": t.subject, "status": t.status} for t in rows]
