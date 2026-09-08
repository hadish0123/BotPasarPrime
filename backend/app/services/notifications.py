from sqlalchemy import select

from app.models.entities import Notification


async def enqueue(db, tenant_id, user_id, kind, title, body, key):
    existing = await db.scalar(select(Notification).where(Notification.idempotency_key == key))
    if existing:
        return False

    db.add(
        Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            idempotency_key=key,
        )
    )
    return True
