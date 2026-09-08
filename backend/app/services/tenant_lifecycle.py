from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_security import require_business_context
from app.models import AuditLog, Tenant


async def soft_delete_tenant(
    session: AsyncSession,
    tenant_id: int,
    context,
    actor_id: int | None = None,
) -> Tenant:
    scope = require_business_context(context)
    scope.require_tenant(tenant_id)

    result = await session.execute(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_deleted.is_(False),
        )
    )

    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise ValueError("Tenant not found")

    tenant.is_deleted = True
    tenant.status = "deleted"

    audit = AuditLog(
        tenant_id=tenant.id,
        actor_type="platform_owner" if scope.is_platform_owner else "tenant_admin",
        actor_id=actor_id,
        action="tenant.soft_delete",
        target_type="Tenant",
        target_id=tenant.id,
        metadata_json={
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    session.add(audit)
    await session.flush()

    return tenant
