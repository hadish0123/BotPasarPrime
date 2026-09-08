from app.models.entities import Broadcast


async def queue_broadcast(db, tenant_id, body):
    broadcast = Broadcast(
        tenant_id=tenant_id,
        body=body,
    )
    db.add(broadcast)
    await db.flush()
    return broadcast
