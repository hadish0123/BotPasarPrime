from app.api.v1.contracts import (
    API_ENDPOINTS,
    AuthenticationRequired,
    AuthorizationDenied,
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

for _path, methods in openapi["paths"].items():
    for _method, operation in methods.items():
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
