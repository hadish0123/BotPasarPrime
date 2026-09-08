from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TicketCreate
from app.core.db import get_db
from app.models.entities import Ticket, TicketMessage

r = APIRouter(prefix="/support", tags=["support"])


@r.post("/tickets")
async def create(x: TicketCreate, tenant_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    t = Ticket(tenant_id=tenant_id, user_id=user_id, subject=x.subject)
    db.add(t)
    await db.flush()
    db.add(TicketMessage(ticket_id=t.id, sender_type="user", body=x.body))
    await db.commit()
    return {"id": t.id, "status": t.status}
