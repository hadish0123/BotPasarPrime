from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.architecture.contracts import (
    CrossTenantAccessError,
    MissingTenantContextError,
    TenantContext,
    require_tenant_context,
)
from app.models import Tenant
from app.security.crypto import box


@dataclass(frozen=True)
class TenantScope:
    tenant_id: int
    is_platform_owner: bool = False

    @classmethod
    def from_context(
        cls,
        context: TenantContext,
        is_platform_owner: bool = False,
    ) -> TenantScope:
        return cls(
            tenant_id=context.tenant_id,
            is_platform_owner=is_platform_owner,
        )

    def require_tenant(self, tenant_id: int) -> None:
        if self.is_platform_owner:
            return
        if tenant_id != self.tenant_id:
            raise CrossTenantAccessError("Cross-tenant access denied")


def require_business_context(
    context: TenantContext | None,
    is_platform_owner: bool = False,
) -> TenantScope:
    if context is None:
        raise MissingTenantContextError("Tenant context is required for business queries")
    require_tenant_context(context)
    return TenantScope.from_context(
        context,
        is_platform_owner=is_platform_owner,
    )


def scope_select(
    statement: Select[Any],
    model: Any,
    context: TenantContext | None,
) -> Select[Any]:
    scope = require_business_context(context)

    if scope.is_platform_owner:
        return statement

    if not hasattr(model, "tenant_id"):
        raise TypeError(f"{model.__name__} is not a tenant-scoped business entity")

    return statement.where(model.tenant_id == scope.tenant_id)


def require_entity_tenant(
    entity: Any,
    context: TenantContext | None,
) -> TenantScope:
    scope = require_business_context(context)

    tenant_id = getattr(entity, "tenant_id", None)

    if tenant_id is None:
        raise TypeError(f"{type(entity).__name__} has no tenant_id")

    scope.require_tenant(tenant_id)
    return scope


async def get_tenant(
    session: AsyncSession,
    tenant_id: int,
    context: TenantContext | None,
) -> Tenant | None:
    scope = require_business_context(context)
    scope.require_tenant(tenant_id)

    statement = select(Tenant).where(
        Tenant.id == tenant_id,
        Tenant.is_deleted.is_(False),
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def soft_delete_tenant(
    session: AsyncSession,
    tenant_id: int,
    context: TenantContext | None,
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

    await session.flush()
    return tenant


def decrypt_credential(
    encrypted_value: str,
    context: TenantContext | None,
    tenant_id: int,
) -> str:
    scope = require_business_context(context)
    scope.require_tenant(tenant_id)

    return box.decrypt(encrypted_value)


def assert_tenant_payload(
    payload: dict[str, Any],
    context: TenantContext | None,
) -> None:
    scope = require_business_context(context)

    payload_tenant_id = payload.get("tenant_id")

    if payload_tenant_id is not None:
        scope.require_tenant(int(payload_tenant_id))


def sanitize_exception_message(message: str) -> str:
    sensitive_words = (
        "token",
        "password",
        "secret",
        "credential",
        "authorization",
        "bearer",
        "api_key",
        "api-token",
    )

    lowered = message.lower()

    if any(word in lowered for word in sensitive_words):
        return "Sensitive operation failed"

    return message[:500]


__all__ = [
    "TenantScope",
    "require_business_context",
    "scope_select",
    "require_entity_tenant",
    "get_tenant",
    "soft_delete_tenant",
    "decrypt_credential",
    "assert_tenant_payload",
    "sanitize_exception_message",
]
