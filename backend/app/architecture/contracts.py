"""
3XSHOP - System Architecture Contract
=====================================

GitBook Page 2: معماری سیستم

Telegram User
   │
   ├── Central Bot
   │     ├── Representative PRIMEVPN
   │     └── Own Panel
   │
   └── Tenant Bot + Mini App
           │
       Multi-Tenant API
           │
       Tenant Database
           │
       PasarGuard Connector

Core platform components:
- Central Bot
- Core Backend
- Tenant Bot Runtime
- Mini App
- PasarGuard Connector
- Database
- Scheduler

Critical architectural rule:
Tenant data MUST be isolated from every other tenant.

Critical dependency rule:
PasarGuard is an external integration and MUST NOT become the runtime
dependency of the 3XSHOP core platform.
"""

from __future__ import annotations

from enum import StrEnum


class ArchitectureComponent(StrEnum):
    CENTRAL_BOT = "central_bot"
    CORE_BACKEND = "core_backend"
    TENANT_BOT_RUNTIME = "tenant_bot_runtime"
    MINI_APP = "mini_app"
    PASARGUARD_CONNECTOR = "pasarguard_connector"
    DATABASE = "database"
    SCHEDULER = "scheduler"


class TenantIsolationError(RuntimeError):
    """Raised when an operation crosses tenant boundaries."""


class MissingTenantContextError(TenantIsolationError):
    """Raised when tenant-scoped work has no tenant context."""


class CrossTenantAccessError(TenantIsolationError):
    """Raised when data is accessed for another tenant."""


class ArchitectureContract:
    """
    Immutable high-level rules for the 3XSHOP platform.
    """

    PLATFORM_NAME = "3XSHOP"

    REQUIRED_COMPONENTS = frozenset(
        {
            ArchitectureComponent.CENTRAL_BOT,
            ArchitectureComponent.CORE_BACKEND,
            ArchitectureComponent.TENANT_BOT_RUNTIME,
            ArchitectureComponent.MINI_APP,
            ArchitectureComponent.PASARGUARD_CONNECTOR,
            ArchitectureComponent.DATABASE,
            ArchitectureComponent.SCHEDULER,
        }
    )

    PASARGUARD_IS_EXTERNAL = True
    TENANT_ISOLATION_REQUIRED = True

    @classmethod
    def validate_component(cls, component: str | ArchitectureComponent) -> ArchitectureComponent:
        try:
            normalized = ArchitectureComponent(component)
        except ValueError as exc:
            raise ValueError(f"Unknown 3XSHOP architecture component: {component!r}") from exc

        if normalized not in cls.REQUIRED_COMPONENTS:
            raise ValueError(f"Component {normalized!r} is not part of the current architecture.")

        return normalized


class TenantContext:
    """
    Explicit tenant boundary.

    Every tenant-scoped operation should carry a TenantContext.

    This object deliberately contains only the internal tenant identifier.
    It must never contain or expose PasarGuard credentials.
    """

    __slots__ = ("tenant_id",)

    def __init__(self, tenant_id: int):
        if isinstance(tenant_id, bool) or not isinstance(tenant_id, int):
            raise TypeError("tenant_id must be an integer")

        if tenant_id <= 0:
            raise ValueError("tenant_id must be greater than zero")

        self.tenant_id = tenant_id

    def assert_same(self, tenant_id: int) -> None:
        """
        Prevent accidental cross-tenant access.
        """

        if tenant_id != self.tenant_id:
            raise CrossTenantAccessError(
                f"Tenant boundary violation: context={self.tenant_id}, requested={tenant_id}"
            )

    def __repr__(self) -> str:
        return f"TenantContext(tenant_id={self.tenant_id})"


def require_tenant_context(
    context: TenantContext | None,
) -> TenantContext:
    """
    Require an explicit tenant context before tenant-scoped work.
    """

    if context is None:
        raise MissingTenantContextError("Tenant context is required for tenant-scoped operations.")

    if not isinstance(context, TenantContext):
        raise TypeError("context must be a TenantContext")

    return context


def assert_tenant_access(
    context: TenantContext | None,
    tenant_id: int,
) -> None:
    """
    Validate that a requested tenant belongs to the current context.
    """

    ctx = require_tenant_context(context)
    ctx.assert_same(tenant_id)


def architecture_snapshot() -> dict[str, object]:
    """
    Machine-readable architecture definition.

    Useful for health checks, diagnostics and future admin tooling.
    """

    return {
        "platform": ArchitectureContract.PLATFORM_NAME,
        "pasarguard_external": ArchitectureContract.PASARGUARD_IS_EXTERNAL,
        "tenant_isolation_required": ArchitectureContract.TENANT_ISOLATION_REQUIRED,
        "components": sorted(
            component.value for component in ArchitectureContract.REQUIRED_COMPONENTS
        ),
    }
