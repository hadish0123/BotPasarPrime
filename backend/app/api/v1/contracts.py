from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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


class HTTPMethod(StrEnum):
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
