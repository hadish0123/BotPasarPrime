"""
Compatibility entry point for tenant isolation.

The canonical implementation lives in app.architecture.contracts.
"""

from app.architecture.contracts import (
    CrossTenantAccessError,
    MissingTenantContextError,
    TenantContext,
    TenantIsolationError,
    assert_tenant_access,
    require_tenant_context,
)

__all__ = [
    "TenantContext",
    "TenantIsolationError",
    "MissingTenantContextError",
    "CrossTenantAccessError",
    "require_tenant_context",
    "assert_tenant_access",
]
