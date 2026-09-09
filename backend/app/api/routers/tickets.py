from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.api.schemas import TicketCreate, TicketReply
from app.core.db import get_db
from app.models.entities import Notification, Ticket, TicketMessage

r = APIRouter(prefix="/support", tags=["support"])


@r.post("/tickets")
async def create(x: TicketCreate, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
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
async def list_tickets(tenant_id: int, claims=Depends(require_permission("tickets.read")), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    query = select(Ticket).where(Ticket.tenant_id == tenant_id).order_by(Ticket.id.desc()).limit(100)
    if claims.get("role") in {None, "customer"} and not claims.get("is_platform_owner"):
        query = query.where(Ticket.user_id == int(claims.get("user_id") or claims.get("sub")))
    rows = (await db.scalars(query)).all()
    return [{"id": t.id, "user_id": t.user_id, "subject": t.subject, "status": t.status} for t in rows]


@r.get("/tickets/{ticket_id}")
async def read_ticket(ticket_id: int, tenant_id: int, claims=Depends(require_permission("tickets.read")), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    ticket = await db.scalar(select(Ticket).where(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id))
    if ticket is None:
        raise HTTPException(404, "ticket_not_found")
    current = int(claims.get("user_id") or claims.get("sub"))
    if claims.get("role") in {None, "customer"} and not claims.get("is_platform_owner") and ticket.user_id != current:
        raise HTTPException(403, "forbidden")
    messages = (await db.scalars(select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.id))).all()
    return {"id": ticket.id, "subject": ticket.subject, "status": ticket.status, "messages": [{"id": m.id, "sender_type": m.sender_type, "body": m.body, "created_at": m.created_at} for m in messages]}


@r.post("/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: int, x: TicketReply, tenant_id: int, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    require_tenant_match(tenant_id, claims)
    ticket = await db.scalar(select(Ticket).where(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id))
    if ticket is None:
        raise HTTPException(404, "ticket_not_found")
    current = int(claims.get("user_id") or claims.get("sub"))
    is_customer = ticket.user_id == current and claims.get("role") in {None, "customer"}
    is_support = "tickets.reply" in claims.get("permissions", []) or claims.get("is_platform_owner")
    if not is_customer and not is_support:
        raise HTTPException(403, "forbidden")
    sender_type = "user" if is_customer else "admin"
    db.add(TicketMessage(ticket_id=ticket.id, sender_type=sender_type, body=x.body))
    ticket.status = "open"
    if sender_type == "admin":
        db.add(Notification(tenant_id=tenant_id, user_id=ticket.user_id, kind="ticket_reply", title="پاسخ تیکت", body=f"برای تیکت «{ticket.subject}» پاسخ جدید دارید."))
    await db.commit()
    return {"id": ticket.id, "status": ticket.status}
