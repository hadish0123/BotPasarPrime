from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import BotInstance

r = APIRouter(prefix="/bots", tags=["bots"])


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
    claims: dict,
    requested_tenant: int | None,
) -> None:
    if claims.get("is_platform_owner"):
        if requested_tenant is not None and bot.tenant_id != requested_tenant:
            raise HTTPException(403, "cross-tenant bot access blocked")
        return
    claim_tenant = claims.get("tenant_id")
    if claim_tenant is None or bot.tenant_id != int(claim_tenant):
        raise HTTPException(403, "cross-tenant bot access blocked")
    if requested_tenant is not None:
        require_tenant_match(requested_tenant, claims)


@r.get("")
async def list_bots(
    tenant_id: int | None = None,
    claims=Depends(require_permission("bots.read")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id is not None:
        require_tenant_match(tenant_id, claims)
    elif not claims.get("is_platform_owner"):
        tenant_id = int(claims["tenant_id"])

    query = select(BotInstance).order_by(BotInstance.id.desc())
    if tenant_id is not None:
        query = query.where(BotInstance.tenant_id == tenant_id)
    result = await db.execute(query)
    return [serialize_bot(bot) for bot in result.scalars().all()]


async def _load_bot(
    bot_id: int,
    tenant_id: int | None,
    claims: dict,
    db: AsyncSession,
) -> BotInstance:
    bot = await db.get(BotInstance, bot_id)
    if bot is None:
        raise HTTPException(404, "bot not found")
    assert_bot_tenant(bot, claims, tenant_id)
    return bot


@r.get("/{bot_id}")
async def get_bot(
    bot_id: int,
    tenant_id: int | None = None,
    claims=Depends(require_permission("bots.read")),
    db: AsyncSession = Depends(get_db),
):
    bot = await _load_bot(bot_id, tenant_id, claims, db)
    return serialize_bot(bot)


@r.post("/{bot_id}/start")
async def start_bot(
    bot_id: int,
    tenant_id: int | None = None,
    claims=Depends(require_permission("bots.write")),
    db: AsyncSession = Depends(get_db),
):
    bot = await _load_bot(bot_id, tenant_id, claims, db)
    if bot.status not in {"approved", "stopped", "failed"}:
        raise HTTPException(409, f"bot cannot start from state: {bot.status}")

    from app.bot.runtime import runtime

    try:
        await runtime.start_bot(bot)
    except Exception as exc:
        raise HTTPException(500, "bot failed to start") from exc

    await db.refresh(bot)
    return serialize_bot(bot)


@r.post("/{bot_id}/stop")
async def stop_bot(
    bot_id: int,
    tenant_id: int | None = None,
    claims=Depends(require_permission("bots.write")),
    db: AsyncSession = Depends(get_db),
):
    bot = await _load_bot(bot_id, tenant_id, claims, db)

    from app.bot.runtime import runtime

    try:
        expected_tenant_id = (
            None
            if claims.get("is_platform_owner")
            else int(claims["tenant_id"])
        )
        await runtime.stop_bot(bot.id, expected_tenant_id=expected_tenant_id)
    except PermissionError as exc:
        raise HTTPException(403, "cross-tenant bot control blocked") from exc

    await db.refresh(bot)
    return serialize_bot(bot)


@r.post("/{bot_id}/suspend")
async def suspend_bot(
    bot_id: int,
    tenant_id: int | None = None,
    claims=Depends(require_permission("bots.write")),
    db: AsyncSession = Depends(get_db),
):
    bot = await _load_bot(bot_id, tenant_id, claims, db)

    from app.bot.runtime import runtime

    try:
        expected_tenant_id = (
            None
            if claims.get("is_platform_owner")
            else int(claims["tenant_id"])
        )
        await runtime.suspend_bot(bot.id, expected_tenant_id=expected_tenant_id)
    except PermissionError as exc:
        raise HTTPException(403, "cross-tenant bot control blocked") from exc

    await db.refresh(bot)
    return serialize_bot(bot)


@r.get("/{bot_id}/health")
async def bot_health(
    bot_id: int,
    tenant_id: int | None = None,
    claims=Depends(require_permission("bots.read")),
    db: AsyncSession = Depends(get_db),
):
    bot = await _load_bot(bot_id, tenant_id, claims, db)

    from app.bot.runtime import runtime

    return {
        "id": bot.id,
        "tenant_id": bot.tenant_id,
        "status": bot.status,
        "runtime_status": "running" if runtime.is_running(bot.id) else "stopped",
        "heartbeat_at": bot.heartbeat_at,
        "error_count": int(bot.error_count or 0),
    }
