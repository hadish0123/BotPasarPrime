from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from app.core.config import settings
from app.models.entities import BotInstance, Notification, User
from app.security.crypto import box

log = logging.getLogger("3xshop.notifications")


async def enqueue(db: AsyncSession, tenant_id, user_id, kind, title, body, key):
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


async def deliver_pending(db: AsyncSession, *, limit: int = 50) -> int:
    """Deliver queued in-app notifications through the tenant bot.

    Delivery is best-effort: the durable notification remains in the database when
    Telegram is unavailable, and can be retried on the next scheduler cycle.
    """
    rows = list(
        (
            await db.scalars(
                select(Notification)
                .where(Notification.sent_at.is_(None))
                .order_by(Notification.id)
                .limit(limit)
            )
        ).all()
    )
    delivered = 0
    for notification in rows:
        user = await db.get(User, notification.user_id)
        bot_row = await db.scalar(
            select(BotInstance)
            .where(
                BotInstance.tenant_id == notification.tenant_id,
                BotInstance.status == "running",
            )
            .order_by(BotInstance.id)
        )
        if user is None or bot_row is None:
            continue
        try:
            token = box.decrypt(bot_row.encrypted_token)
            async with Bot(token=token) as bot:
                text = f"<b>{notification.title}</b>\n{notification.body}"
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            notification.sent_at = datetime.now(UTC)
            delivered += 1
        except Exception:
            log.exception(
                "notification delivery failed notification=%s tenant=%s user=%s",
                notification.id,
                notification.tenant_id,
                notification.user_id,
            )
    if delivered:
        await db.commit()
    return delivered
