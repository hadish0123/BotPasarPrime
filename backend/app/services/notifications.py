from __future__ import annotations

import html
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from app.models.entities import BotInstance, Notification, User
from app.security.crypto import box

log = logging.getLogger("3xshop.notifications")


async def enqueue(db: AsyncSession, tenant_id, user_id, kind, title, body, key):
    """Queue a notification exactly once, even under concurrent workers."""
    stmt = (
        insert(Notification)
        .values(
            tenant_id=tenant_id,
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            idempotency_key=key,
        )
        .on_conflict_do_nothing(index_elements=[Notification.idempotency_key])
        .returning(Notification.id)
    )
    inserted_id = await db.scalar(stmt)
    return inserted_id is not None


async def deliver_pending(db: AsyncSession, *, limit: int = 50) -> int:
    """Deliver queued notifications through the tenant bot.

    Queue rows are locked so multiple scheduler workers do not send the same
    notification concurrently. Failed deliveries stay queued for a later cycle.
    """
    rows = list(
        (
            await db.scalars(
                select(Notification)
                .where(Notification.sent_at.is_(None))
                .order_by(Notification.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
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
                title = html.escape(notification.title)
                body = html.escape(notification.body)
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"<b>{title}</b>\n{body}",
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
