from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.db import SessionLocal

r = APIRouter(tags=["system"])


@r.get("/health")
async def health():
    return {"status": "ok", "service": "3XSHOP"}


@r.get("/ready")
async def ready():
    """Readiness probe: the process is ready only when PostgreSQL is reachable."""
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
    return {"status": "ready", "service": "3XSHOP", "database": "ok"}
