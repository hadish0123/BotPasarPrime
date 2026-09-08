from __future__ import annotations

from .base import PasarGuardAdapter, PasarGuardUnsupportedVersion


class PasarGuardV5Adapter(PasarGuardAdapter):
    """
    PasarGuard V5 adapter.

    These paths are isolated here so future PasarGuard API changes
    do not leak into 3XSHOP business logic.
    """

    version = "v5"

    def users_collection(self) -> str:
        return "/api/users"

    def user_resource(self, identifier: str | int) -> str:
        return f"/api/user/{identifier}"

    def user_subscription(self, identifier: str | int) -> str:
        return f"/api/user/{identifier}"

    def build_create_user_payload(self, payload: dict) -> dict:
        return dict(payload)

    def build_update_user_payload(self, payload: dict) -> dict:
        return dict(payload)


_ADAPTERS = {
    "v5": PasarGuardV5Adapter,
}


def get_adapter(version: str) -> PasarGuardAdapter:
    normalized = version.strip().lower().lstrip("v")

    if normalized == "5":
        normalized = "v5"

    adapter = _ADAPTERS.get(normalized)

    if adapter is None:
        raise PasarGuardUnsupportedVersion(f"Unsupported PasarGuard API version: {version}")

    return adapter()
