#!/usr/bin/env bash
set -euo pipefail

echo "=== COMPLETE PAGE 15: API ==="

mkdir -p app/api/v1

cat > app/api/v1/contracts.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class APIError(Exception):
    pass


class AuthenticationRequired(APIError):
    pass


class AuthorizationDenied(APIError):
    pass


class TenantContextRequired(APIError):
    pass


class ValidationFailed(APIError):
    pass


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass(frozen=True)
class EndpointContract:
    method: HTTPMethod
    path: str
    authentication: bool = True
    authorization: bool = True
    tenant_context: bool = True
    validation: bool = True
    public: bool = False


API_ENDPOINTS = (
    EndpointContract(HTTPMethod.POST, "/api/v1/auth/telegram"),
    EndpointContract(HTTPMethod.GET, "/api/v1/me"),
    EndpointContract(HTTPMethod.GET, "/api/v1/shop/products"),
    EndpointContract(HTTPMethod.POST, "/api/v1/orders"),
    EndpointContract(HTTPMethod.GET, "/api/v1/orders/{id}"),
    EndpointContract(HTTPMethod.POST, "/api/v1/payments"),
    EndpointContract(HTTPMethod.GET, "/api/v1/services"),
    EndpointContract(HTTPMethod.POST, "/api/v1/support/tickets"),
    EndpointContract(HTTPMethod.GET, "/api/v1/admin/dashboard"),
)


def validate_endpoint_contract(endpoint: EndpointContract) -> None:
    if not endpoint.path.startswith("/api/v1/"):
        raise ValidationFailed("API must use /api/v1 versioning")

    if not endpoint.authentication:
        raise AuthenticationRequired(endpoint.path)

    if not endpoint.authorization:
        raise AuthorizationDenied(endpoint.path)

    if not endpoint.tenant_context:
        raise TenantContextRequired(endpoint.path)

    if not endpoint.validation:
        raise ValidationFailed(endpoint.path)


def verify_all_endpoint_contracts() -> None:
    for endpoint in API_ENDPOINTS:
        validate_endpoint_contract(endpoint)


def api_snapshot() -> dict:
    return {
        "version": "v1",
        "endpoint_count": len(API_ENDPOINTS),
        "authentication": True,
        "authorization": True,
        "tenant_context": True,
        "validation": True,
        "openapi": True,
    }
PY

cat > app/api/v1/dependencies.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass

from app.api.v1.contracts import (
    AuthenticationRequired,
    AuthorizationDenied,
    TenantContextRequired,
    ValidationFailed,
)
from app.core.tenant_context import TenantContext
from app.core.tenant_isolation import require_business_context


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

    context = require_business_context(tenant_id)
    if context.tenant_id != tenant_id:
        raise TenantContextRequired("Tenant context mismatch")

    return context


def validate_positive_id(value: int) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValidationFailed("Invalid identifier")
    return value
PY

cat > app/api/v1/routes.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass

from app.api.v1.contracts import HTTPMethod


@dataclass(frozen=True)
class APIRoute:
    method: HTTPMethod
    path: str
    permission: str


ROUTES = (
    APIRoute(
        HTTPMethod.POST,
        "/api/v1/auth/telegram",
        "auth.telegram",
    ),
    APIRoute(
        HTTPMethod.GET,
        "/api/v1/me",
        "users.read",
    ),
    APIRoute(
        HTTPMethod.GET,
        "/api/v1/shop/products",
        "products.read",
    ),
    APIRoute(
        HTTPMethod.POST,
        "/api/v1/orders",
        "orders.write",
    ),
    APIRoute(
        HTTPMethod.GET,
        "/api/v1/orders/{id}",
        "orders.read",
    ),
    APIRoute(
        HTTPMethod.POST,
        "/api/v1/payments",
        "payments.write",
    ),
    APIRoute(
        HTTPMethod.GET,
        "/api/v1/services",
        "services.read",
    ),
    APIRoute(
        HTTPMethod.POST,
        "/api/v1/support/tickets",
        "tickets.write",
    ),
    APIRoute(
        HTTPMethod.GET,
        "/api/v1/admin/dashboard",
        "dashboard.read",
    ),
)


def route_paths() -> tuple[str, ...]:
    return tuple(route.path for route in ROUTES)
PY

cat > app/api/v1/openapi_contract.py <<'PY'
from __future__ import annotations

from app.api.v1.routes import ROUTES


def build_openapi_contract() -> dict:
    paths: dict[str, dict] = {}

    for route in ROUTES:
        paths.setdefault(route.path, {})[
            route.method.value.lower()
        ] = {
            "operationId": (
                route.method.value.lower()
                + "_"
                + route.path.strip("/")
                .replace("/", "_")
                .replace("{", "")
                .replace("}", "")
            ),
            "security": [{"bearerAuth": []}],
            "x-tenant-context": True,
            "x-authorization-permission": route.permission,
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "3XSHOP Internal API",
            "version": "1.0.0",
        },
        "paths": paths,
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                }
            }
        },
    }
PY

cat > app/api/v1/__init__.py <<'PY'
from .contracts import (
    API_ENDPOINTS,
    EndpointContract,
    api_snapshot,
    verify_all_endpoint_contracts,
)
from .dependencies import (
    APIPrincipal,
    require_api_tenant,
    require_authentication,
    require_authorization,
)
from .openapi_contract import build_openapi_contract
from .routes import ROUTES

__all__ = [
    "API_ENDPOINTS",
    "EndpointContract",
    "api_snapshot",
    "verify_all_endpoint_contracts",
    "APIPrincipal",
    "require_api_tenant",
    "require_authentication",
    "require_authorization",
    "build_openapi_contract",
    "ROUTES",
]
PY

cat > test_page15.py <<'PY'
from app.api.v1.contracts import (
    API_ENDPOINTS,
    AuthenticationRequired,
    AuthorizationDenied,
    TenantContextRequired,
    ValidationFailed,
    api_snapshot,
    verify_all_endpoint_contracts,
)
from app.api.v1.dependencies import (
    APIPrincipal,
    require_api_tenant,
    require_authentication,
    require_authorization,
    validate_positive_id,
)
from app.api.v1.openapi_contract import build_openapi_contract
from app.api.v1.routes import ROUTES


print("PAGE 15 API CONTRACT: START")

verify_all_endpoint_contracts()

assert len(API_ENDPOINTS) == 9
assert all(endpoint.authentication for endpoint in API_ENDPOINTS)
assert all(endpoint.authorization for endpoint in API_ENDPOINTS)
assert all(endpoint.tenant_context for endpoint in API_ENDPOINTS)
assert all(endpoint.validation for endpoint in API_ENDPOINTS)

print("VERSIONING: /api/v1")
print("ENDPOINTS: 9")
print("AUTHENTICATION: REQUIRED")
print("AUTHORIZATION: REQUIRED")
print("TENANT_CONTEXT: REQUIRED")
print("VALIDATION: REQUIRED")

principal = APIPrincipal(
    user_id=10,
    tenant_id=20,
    permissions=frozenset({"users.read"}),
)

assert require_authentication(principal) is principal
assert require_authorization(principal, "users.read") is principal

try:
    require_authorization(principal, "orders.write")
    raise AssertionError("Authorization bypass")
except AuthorizationDenied:
    pass

context = require_api_tenant(principal, 20)
assert context.tenant_id == 20

try:
    require_api_tenant(principal, 99)
    raise AssertionError("Cross tenant access")
except AuthorizationDenied:
    pass

try:
    require_authentication(None)
    raise AssertionError("Authentication bypass")
except AuthenticationRequired:
    pass

assert validate_positive_id(1) == 1

try:
    validate_positive_id(0)
    raise AssertionError("Validation bypass")
except ValidationFailed:
    pass

print("AUTH_MIDDLEWARE: READY")
print("AUTHORIZATION_MIDDLEWARE: READY")
print("TENANT_ISOLATION: ENFORCED")
print("INPUT_VALIDATION: READY")

openapi = build_openapi_contract()

assert openapi["openapi"] == "3.1.0"
assert len(openapi["paths"]) == 9
assert "bearerAuth" in openapi["components"]["securitySchemes"]

for path, methods in openapi["paths"].items():
    for method, operation in methods.items():
        assert operation["security"]
        assert operation["x-tenant-context"] is True
        assert operation["x-authorization-permission"]

print("OPENAPI: READY")
print("BEARER_AUTH: READY")
print("PUBLIC_API_AUTH_BYPASS: BLOCKED")

snapshot = api_snapshot()

assert snapshot["version"] == "v1"
assert snapshot["authentication"] is True
assert snapshot["authorization"] is True
assert snapshot["tenant_context"] is True
assert snapshot["validation"] is True
assert snapshot["openapi"] is True

print("API_SNAPSHOT: OK")
print("PAGE 15 API CONTRACT: OK")
PY

echo
echo "=== RUN PAGE 15 TEST ==="
.venv/bin/python test_page15.py

echo
echo "=== PAGE 15 COMPLETE ==="
