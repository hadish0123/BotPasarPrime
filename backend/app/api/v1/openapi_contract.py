from __future__ import annotations

from app.api.v1.routes import ROUTES


def build_openapi_contract() -> dict:
    paths: dict[str, dict] = {}

    for route in ROUTES:
        paths.setdefault(route.path, {})[route.method.value.lower()] = {
            "operationId": (
                route.method.value.lower()
                + "_"
                + route.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
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
