from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.db import get_db
from app.models.entities import AuditLog

r = APIRouter(prefix="/audit", tags=["audit"])


@r.get("")
async def logs(
    tenant_id: int | None = None,
    claims=Depends(require_permission("audit.read")),
    db: AsyncSession = Depends(get_db),
    limit: int = 200,
):
    is_owner = bool(claims.get("is_platform_owner"))
    if tenant_id is not None and tenant_id <= 0:
        raise HTTPException(status_code=400, detail="invalid tenant")
    if not is_owner:
        claim_tenant = claims.get("tenant_id")
        if claim_tenant is None:
            raise HTTPException(status_code=403, detail="tenant context required")
        if tenant_id is None:
            tenant_id = int(claim_tenant)
        elif int(claim_tenant) != int(tenant_id):
            raise HTTPException(status_code=403, detail="cross-tenant access denied")

    limit = max(1, min(limit, 200))
    query = select(AuditLog)
    if tenant_id is not None:
        query = query.where(AuditLog.tenant_id == tenant_id)
    query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    rows = (await db.scalars(query)).all()

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
