from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class PasarGuardConnectorError(Exception):
    """Base connector error."""


class PasarGuardAuthenticationError(PasarGuardConnectorError):
    """Authentication or credential failure."""


class PasarGuardConnectionError(PasarGuardConnectorError):
    """Network/connectivity failure."""


class PasarGuardAPIError(PasarGuardConnectorError):
    """Remote API returned an error."""


class PasarGuardUnsupportedVersion(PasarGuardConnectorError):
    """Unsupported PasarGuard API version."""


@dataclass(frozen=True)
class PasarGuardCredentials:
    base_url: str
    api_token: str
    username: str | None = None

    def __post_init__(self) -> None:
        base = self.base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ValueError("PasarGuard base_url must use http:// or https://")

        if not self.api_token.strip():
            raise ValueError("PasarGuard API token is required")

        object.__setattr__(self, "base_url", base)
        object.__setattr__(self, "api_token", self.api_token.strip())

        if self.username is not None:
            username = self.username.strip()
            object.__setattr__(self, "username", username or None)


@dataclass(frozen=True)
class PasarGuardUser:
    id: int | str | None
    username: str
    status: str | None
    data_limit: int | None
    expire: str | None
    subscription_url: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class PasarGuardHealth:
    ok: bool
    version: str | None
    latency_ms: float | None
    detail: str | None = None


class PasarGuardAdapter(ABC):
    """
    Version-specific API adapter.

    Business logic must depend on this interface, never on raw
    PasarGuard endpoint strings.
    """

    version: str = "unknown"

    @abstractmethod
    def users_collection(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def user_resource(self, identifier: str | int) -> str:
        raise NotImplementedError

    @abstractmethod
    def user_subscription(self, identifier: str | int) -> str:
        raise NotImplementedError

    def build_create_user_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(payload)

    def build_update_user_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(payload)

    def normalize_user(self, data: dict[str, Any]) -> PasarGuardUser:
        return PasarGuardUser(
            id=data.get("id"),
            username=str(data.get("username", "")),
            status=data.get("status"),
            data_limit=data.get("data_limit"),
            expire=data.get("expire"),
            subscription_url=data.get("subscription_url"),
            raw=data,
        )
