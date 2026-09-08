from __future__ import annotations

from dataclasses import dataclass

from app.api.v1.contracts import (
    AuthenticationRequired,
    AuthorizationDenied,
    TenantContextRequired,
    ValidationFailed,
)
from app.core.tenant_context import TenantContext


@dataclass(frozen=True)
class APIPrincipal:
    user_id: int
    tenant_id: int
    is_authenticated: bool = True
    permissions: frozenset[str] = frozenset()


def require_authentication(
    principal: APIPrincipal | None,
) -> APIPrincipal:
    if principal is None or not principal.is_authenticated:
        raise AuthenticationRequired("Authentication required")
    return principal


def require_authorization(
    principal: APIPrincipal,
    permission: str,
) -> APIPrincipal:
    principal = require_authentication(principal)

    if permission not in principal.permissions:
        raise AuthorizationDenied(permission)

    return principal


def require_api_tenant(
    principal: APIPrincipal,
    tenant_id: int,
) -> TenantContext:
    principal = require_authentication(principal)

    if principal.tenant_id != tenant_id:
        raise AuthorizationDenied("Cross-tenant access denied")

    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise TenantContextRequired("Invalid tenant context")

    context = TenantContext(tenant_id=tenant_id)

    if context.tenant_id != tenant_id:
        raise TenantContextRequired("Tenant context mismatch")

    return context


def validate_positive_id(value: int) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValidationFailed("Invalid identifier")

    return value
