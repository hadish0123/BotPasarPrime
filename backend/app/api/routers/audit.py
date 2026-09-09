from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import AuditLog

r = APIRouter(prefix="/audit", tags=["audit"])


@r.get("")
async def logs(
    tenant_id: int,
    claims=Depends(require_permission("audit.read")),
    db: AsyncSession = Depends(get_db),
    limit: int = 200,
):
    if tenant_id <= 0:
        raise HTTPException(status_code=400, detail="invalid tenant")
    require_tenant_match(tenant_id, claims)
    limit = max(1, min(limit, 200))
    rows = (
        await db.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        )
    ).all()

    return [
        {
            "id": row.id,
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "tenant_id": row.tenant_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "timestamp": row.created_at,
            "metadata": row.metadata_json,
        }
        for row in rows
    ]
