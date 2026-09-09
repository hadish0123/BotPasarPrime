from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import settings

_LOCK_KEY = 3_203_250_001
_engine = None
_connection: AsyncConnection | None = None


async def acquire_bot_leader() -> bool:
    global _engine, _connection
    if _connection is not None:
        return True
    _engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    _connection = await _engine.connect()
    result = await _connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY})
    if not bool(result.scalar()):
        await _connection.close()
        await _engine.dispose()
        _connection = None
        _engine = None
        return False
    return True


async def release_bot_leader() -> None:
    global _engine, _connection
    if _connection is None:
        return
    try:
        await _connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
    finally:
        await _connection.close()
        if _engine is not None:
            await _engine.dispose()
        _connection = None
        _engine = None
