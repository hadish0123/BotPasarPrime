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
