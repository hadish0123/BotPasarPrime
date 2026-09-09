from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from telegram import Update
from telegram.ext import Application

from app.core.db import SessionLocal
from app.models.entities import BotInstance
from app.security.crypto import box

log = logging.getLogger("3xshop.bot-runtime")


class BotRuntimeState(StrEnum):
    REGISTERED = "registered"
    PENDING = "pending"
    APPROVED = "approved"
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    SUSPENDED = "suspended"


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    BotRuntimeState.REGISTERED: {BotRuntimeState.PENDING, BotRuntimeState.APPROVED, BotRuntimeState.SUSPENDED},
    BotRuntimeState.PENDING: {BotRuntimeState.APPROVED, BotRuntimeState.SUSPENDED},
    BotRuntimeState.APPROVED: {BotRuntimeState.STARTING, BotRuntimeState.SUSPENDED, BotRuntimeState.STOPPED},
    BotRuntimeState.STARTING: {BotRuntimeState.RUNNING, BotRuntimeState.FAILED, BotRuntimeState.SUSPENDED},
    BotRuntimeState.RUNNING: {BotRuntimeState.STOPPED, BotRuntimeState.FAILED, BotRuntimeState.SUSPENDED},
    BotRuntimeState.STOPPED: {BotRuntimeState.STARTING, BotRuntimeState.SUSPENDED},
    BotRuntimeState.FAILED: {BotRuntimeState.STARTING, BotRuntimeState.STOPPED, BotRuntimeState.SUSPENDED},
    BotRuntimeState.SUSPENDED: {BotRuntimeState.APPROVED, BotRuntimeState.STOPPED},
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def transition_allowed(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: str, target: str) -> None:
    if not transition_allowed(current, target):
        raise ValueError(f"invalid bot lifecycle transition: {current} -> {target}")


class BotRuntime:
    def __init__(self) -> None:
        self.instances: dict[int, Application] = {}
        self.tasks: dict[int, asyncio.Task[Any]] = {}
        self.lock = asyncio.Lock()

    async def _set_state(self, bot_id: int, target: str, *, increment_error: bool = False) -> None:
        async with SessionLocal() as db:
            bot = await db.get(BotInstance, bot_id)
            if bot is None:
                return
            current = bot.status
            try:
                assert_transition(current, target)
            except ValueError:
                log.warning("blocked invalid lifecycle transition bot=%s %s -> %s", bot_id, current, target)
                return
            bot.status = target
            if target == BotRuntimeState.RUNNING:
                bot.heartbeat_at = utc_now()
            if increment_error:
                bot.error_count = int(bot.error_count or 0) + 1
            await db.commit()

    async def _mark_heartbeat(self, bot_id: int) -> None:
        async with SessionLocal() as db:
            bot = await db.get(BotInstance, bot_id)
            if bot is None:
                return
            if bot.status == BotRuntimeState.RUNNING:
                bot.heartbeat_at = utc_now()
                await db.commit()

    async def _heartbeat_loop(self, bot_id: int) -> None:
        while True:
            try:
                await asyncio.sleep(30)
                if bot_id not in self.instances:
                    return
                await self._mark_heartbeat(bot_id)
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("heartbeat failure bot=%s", bot_id)

    async def start_bot(self, bot: BotInstance) -> None:
        if bot.tenant_id is None:
            raise ValueError(f"tenant bot {bot.id} has no tenant_id")
        async with self.lock:
            if bot.id in self.instances:
                return
            if bot.status not in {BotRuntimeState.APPROVED, BotRuntimeState.RUNNING, BotRuntimeState.STOPPED, BotRuntimeState.FAILED}:
                raise ValueError(f"bot cannot start from state: {bot.status}")
            if bot.status == BotRuntimeState.RUNNING:
                bot.status = BotRuntimeState.STOPPED
            await self._set_state(bot.id, BotRuntimeState.STARTING)
            application: Application | None = None
            try:
                token = box.decrypt(bot.encrypted_token)
                from app.bot.tenant import build_tenant_application
                application = build_tenant_application(token=token, tenant_id=int(bot.tenant_id), bot_instance_id=int(bot.id))
                await application.initialize()
                await application.start()
                if application.updater is None:
                    raise RuntimeError("tenant bot updater is unavailable")
                await application.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
                self.instances[bot.id] = application
                self.tasks[bot.id] = asyncio.create_task(self._heartbeat_loop(bot.id), name=f"3xshop-bot-heartbeat-{bot.id}")
                await self._set_state(bot.id, BotRuntimeState.RUNNING)
                log.info("tenant bot started bot_id=%s tenant_id=%s", bot.id, bot.tenant_id)
            except Exception:
                if application is not None:
                    try:
                        if application.updater and application.updater.running:
                            await application.updater.stop()
                    except Exception:
                        log.exception("tenant bot updater cleanup failed bot=%s", bot.id)
                    try:
                        await application.stop()
                    except Exception:
                        log.exception("tenant bot stop cleanup failed bot=%s", bot.id)
                    try:
                        await application.shutdown()
                    except Exception:
                        log.exception("tenant bot shutdown cleanup failed bot=%s", bot.id)
                await self._set_state(bot.id, BotRuntimeState.FAILED, increment_error=True)
                raise

    async def stop_bot(self, bot_id: int, *, expected_tenant_id: int | None = None) -> None:
        async with self.lock:
            application = self.instances.get(bot_id)
            async with SessionLocal() as db:
                bot = await db.get(BotInstance, bot_id)
                if bot is None:
                    raise ValueError("bot not found")
                if expected_tenant_id is not None and bot.tenant_id != expected_tenant_id:
                    raise PermissionError("cross-tenant bot control blocked")
            if application is None:
                await self._set_state(bot_id, BotRuntimeState.STOPPED)
                return
            self.instances.pop(bot_id, None)
            task = self.tasks.pop(bot_id, None)
            if task is not None:
                task.cancel()
            try:
                if application.updater and application.updater.running:
                    await application.updater.stop()
                await application.stop()
                await application.shutdown()
            finally:
                await self._set_state(bot_id, BotRuntimeState.STOPPED)

    async def suspend_bot(self, bot_id: int, *, expected_tenant_id: int | None = None) -> None:
        async with SessionLocal() as db:
            bot = await db.get(BotInstance, bot_id)
            if bot is None:
                raise ValueError("bot not found")
            if expected_tenant_id is not None and bot.tenant_id != expected_tenant_id:
                raise PermissionError("cross-tenant bot control blocked")
        await self.stop_bot(bot_id, expected_tenant_id=expected_tenant_id)
        await self._set_state(bot_id, BotRuntimeState.SUSPENDED)

    async def start_approved_bots(self) -> None:
        async with SessionLocal() as db:
            result = await db.execute(select(BotInstance).where(BotInstance.status.in_([BotRuntimeState.APPROVED, BotRuntimeState.RUNNING])))
            bots = list(result.scalars().all())
        for bot in bots:
            if bot.id in self.instances:
                continue
            try:
                await self.start_bot(bot)
            except Exception:
                log.exception("failed to restore tenant bot bot=%s", bot.id)

    async def shutdown_all(self) -> None:
        for bot_id in list(self.instances.keys()):
            try:
                await self.stop_bot(bot_id)
            except Exception:
                log.exception("failed to stop bot during runtime shutdown bot=%s", bot_id)

    def health(self, bot_id: int, *, expected_tenant_id: int | None = None) -> dict[str, Any]:
        application = self.instances.get(bot_id)
        if expected_tenant_id is not None:
            raise ValueError("health requires database tenant validation")
        return {"id": bot_id, "running": application is not None, "runtime_status": BotRuntimeState.RUNNING.value if application is not None else BotRuntimeState.STOPPED.value}

    def is_running(self, bot_id: int) -> bool:
        return bot_id in self.instances


runtime = BotRuntime()
