from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.entities import BotInstance

r = APIRouter(
    prefix="/bots",
    tags=["bots"],
)


def serialize_bot(bot: BotInstance) -> dict:
    return {
        "id": bot.id,
        "tenant_id": bot.tenant_id,
        "name": bot.name,
        "masked_token": bot.masked_token,
        "status": bot.status,
        "heartbeat_at": bot.heartbeat_at,
        "error_count": int(bot.error_count or 0),
    }


def assert_bot_tenant(
    bot: BotInstance,
    tenant_id: int | None,
) -> None:
    if tenant_id is None:
        return

    if bot.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="cross-tenant bot access blocked",
        )


@r.get("")
async def list_bots(
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(BotInstance).order_by(BotInstance.id.desc())

    if tenant_id is not None:
        query = query.where(BotInstance.tenant_id == tenant_id)

    result = await db.execute(query)

    return [serialize_bot(bot) for bot in result.scalars().all()]


@r.get("/{bot_id}")
async def get_bot(
    bot_id: int,
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(
        BotInstance,
        bot_id,
    )

    if bot is None:
        raise HTTPException(
            status_code=404,
            detail="bot not found",
        )

    assert_bot_tenant(
        bot,
        tenant_id,
    )

    return serialize_bot(bot)


@r.post("/{bot_id}/start")
async def start_bot(
    bot_id: int,
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(
        BotInstance,
        bot_id,
    )

    if bot is None:
        raise HTTPException(
            status_code=404,
            detail="bot not found",
        )

    assert_bot_tenant(
        bot,
        tenant_id,
    )

    if bot.status not in {
        "approved",
        "stopped",
        "failed",
    }:
        raise HTTPException(
            status_code=409,
            detail=f"bot cannot start from state: {bot.status}",
        )

    from app.bot.runtime import runtime

    try:
        await runtime.start_bot(bot)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="bot failed to start",
        ) from exc

    return {
        "id": bot.id,
        "tenant_id": bot.tenant_id,
        "status": "running",
    }


@r.post("/{bot_id}/stop")
async def stop_bot(
    bot_id: int,
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(
        BotInstance,
        bot_id,
    )

    if bot is None:
        raise HTTPException(
            status_code=404,
            detail="bot not found",
        )

    assert_bot_tenant(
        bot,
        tenant_id,
    )

    from app.bot.runtime import runtime

    try:
        await runtime.stop_bot(
            bot.id,
            expected_tenant_id=tenant_id,
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="cross-tenant bot control blocked",
        ) from exc

    await db.refresh(bot)

    return {
        "id": bot.id,
        "tenant_id": bot.tenant_id,
        "status": bot.status,
    }


@r.post("/{bot_id}/suspend")
async def suspend_bot(
    bot_id: int,
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(
        BotInstance,
        bot_id,
    )

    if bot is None:
        raise HTTPException(
            status_code=404,
            detail="bot not found",
        )

    assert_bot_tenant(
        bot,
        tenant_id,
    )

    from app.bot.runtime import runtime

    try:
        await runtime.suspend_bot(
            bot.id,
            expected_tenant_id=tenant_id,
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="cross-tenant bot control blocked",
        ) from exc

    await db.refresh(bot)

    return {
        "id": bot.id,
        "tenant_id": bot.tenant_id,
        "status": bot.status,
    }


@r.get("/{bot_id}/health")
async def bot_health(
    bot_id: int,
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    bot = await db.get(
        BotInstance,
        bot_id,
    )

    if bot is None:
        raise HTTPException(
            status_code=404,
            detail="bot not found",
        )

    assert_bot_tenant(
        bot,
        tenant_id,
    )

    from app.bot.runtime import runtime

    return {
        "id": bot.id,
        "tenant_id": bot.tenant_id,
        "status": bot.status,
        "runtime_status": ("running" if runtime.is_running(bot.id) else "stopped"),
        "heartbeat_at": bot.heartbeat_at,
        "error_count": int(bot.error_count or 0),
    }
