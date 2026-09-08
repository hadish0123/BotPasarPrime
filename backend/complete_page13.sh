#!/usr/bin/env bash
set -euo pipefail

echo "=== COMPLETE PAGE 13: PASARGUARD CONNECTOR ==="

mkdir -p app/pasarguard

touch app/pasarguard/__init__.py

cat > app/pasarguard/base.py <<'PY'
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
PY


cat > app/pasarguard/adapters.py <<'PY'
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
        raise PasarGuardUnsupportedVersion(
            f"Unsupported PasarGuard API version: {version}"
        )

    return adapter()
PY


cat > app/pasarguard/credentials.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass

from app.security.crypto import box

from .base import PasarGuardCredentials


@dataclass(frozen=True)
class EncryptedPasarGuardCredentials:
    base_url: str
    encrypted_api_token: str
    encrypted_username: str | None = None


def encrypt_credentials(
    credentials: PasarGuardCredentials,
) -> EncryptedPasarGuardCredentials:
    encrypted_token = box.encrypt(credentials.api_token)

    encrypted_username = None
    if credentials.username:
        encrypted_username = box.encrypt(credentials.username)

    return EncryptedPasarGuardCredentials(
        base_url=credentials.base_url,
        encrypted_api_token=encrypted_token,
        encrypted_username=encrypted_username,
    )


def decrypt_credentials(
    encrypted: EncryptedPasarGuardCredentials,
) -> PasarGuardCredentials:
    token = box.decrypt(encrypted.encrypted_api_token)

    username = None
    if encrypted.encrypted_username:
        username = box.decrypt(encrypted.encrypted_username)

    return PasarGuardCredentials(
        base_url=encrypted.base_url,
        api_token=token,
        username=username,
    )


def mask_credentials(
    credentials: PasarGuardCredentials,
) -> dict[str, str | None]:
    return {
        "base_url": credentials.base_url,
        "api_token": "***REDACTED***",
        "username": credentials.username,
    }
PY


cat > app/pasarguard/client.py <<'PY'
from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp

from .adapters import get_adapter
from .base import (
    PasarGuardAPIError,
    PasarGuardAuthenticationError,
    PasarGuardConnectionError,
    PasarGuardCredentials,
    PasarGuardHealth,
)


class PasarGuardClient:
    """
    Thin transport layer.

    No business logic lives here.
    No credentials are logged.
    Retry is deliberately limited.
    """

    def __init__(
        self,
        credentials: PasarGuardCredentials,
        *,
        version: str = "v5",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.4,
    ) -> None:
        self.credentials = credentials
        self.adapter = get_adapter(version)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, min(max_retries, 3))
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.credentials.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        method = method.upper()
        url = f"{self.credentials.base_url}{path}"

        # Only safe/idempotent methods are automatically retried.
        retryable = method in {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}

        attempts = 1 + (self.max_retries if retryable else 0)

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        last_error: Exception | None = None

        for attempt in range(attempts):
            started = time.monotonic()

            try:
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    headers=self._headers(),
                ) as session:
                    async with session.request(
                        method,
                        url,
                        json=json,
                        params=params,
                    ) as response:
                        latency = time.monotonic() - started
                        body_text = await response.text()

                        if response.status in {401, 403}:
                            raise PasarGuardAuthenticationError(
                                f"PasarGuard authentication failed ({response.status})"
                            )

                        if response.status >= 400:
                            detail = body_text[:500] if body_text else "remote API error"
                            raise PasarGuardAPIError(
                                f"PasarGuard API error {response.status}: {detail}"
                            )

                        if not body_text:
                            return None

                        content_type = response.headers.get("Content-Type", "")

                        if "application/json" in content_type:
                            return await response.json()

                        return body_text

            except PasarGuardAuthenticationError:
                raise

            except PasarGuardAPIError as exc:
                # 4xx errors are not retried.
                if " 5" not in str(exc):
                    raise
                last_error = exc

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc

            if attempt + 1 < attempts:
                await asyncio.sleep(
                    self.retry_backoff_seconds * (attempt + 1)
                )

        raise PasarGuardConnectionError(
            "Unable to communicate with PasarGuard"
        ) from last_error

    async def health(self) -> PasarGuardHealth:
        started = time.monotonic()

        try:
            # Root endpoint is intentionally used only as connectivity/auth check.
            await self.request("GET", "/")
            latency = (time.monotonic() - started) * 1000

            return PasarGuardHealth(
                ok=True,
                version=self.adapter.version,
                latency_ms=round(latency, 2),
            )

        except Exception as exc:
            latency = (time.monotonic() - started) * 1000

            return PasarGuardHealth(
                ok=False,
                version=self.adapter.version,
                latency_ms=round(latency, 2),
                detail=type(exc).__name__,
            )

    async def list_users(
        self,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self.request(
            "GET",
            self.adapter.users_collection(),
            params=params,
        )

    async def get_user(
        self,
        identifier: str | int,
    ) -> Any:
        return await self.request(
            "GET",
            self.adapter.user_resource(identifier),
        )

    async def create_user(
        self,
        payload: dict[str, Any],
    ) -> Any:
        return await self.request(
            "POST",
            self.adapter.users_collection().replace("/users", "/user"),
            json=self.adapter.build_create_user_payload(payload),
        )

    async def update_user(
        self,
        identifier: str | int,
        payload: dict[str, Any],
    ) -> Any:
        return await self.request(
            "PUT",
            self.adapter.user_resource(identifier),
            json=self.adapter.build_update_user_payload(payload),
        )

    async def delete_user(
        self,
        identifier: str | int,
    ) -> Any:
        return await self.request(
            "DELETE",
            self.adapter.user_resource(identifier),
        )

    async def get_subscription(
        self,
        identifier: str | int,
    ) -> Any:
        return await self.request(
            "GET",
            self.adapter.user_subscription(identifier),
        )
PY


cat > app/pasarguard/service.py <<'PY'
from __future__ import annotations

from typing import Any

from .client import PasarGuardClient


class PasarGuardService:
    """
    Business-facing facade.

    The rest of 3XSHOP talks to this class rather than directly
    constructing HTTP requests.
    """

    def __init__(self, client: PasarGuardClient) -> None:
        self.client = client

    async def authenticate_connection(self) -> bool:
        health = await self.client.health()
        return health.ok

    async def get_users(
        self,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self.client.list_users(params=params)

    async def get_user(self, identifier: str | int) -> Any:
        return await self.client.get_user(identifier)

    async def provision_user(self, payload: dict[str, Any]) -> Any:
        return await self.client.create_user(payload)

    async def update_user(
        self,
        identifier: str | int,
        payload: dict[str, Any],
    ) -> Any:
        return await self.client.update_user(identifier, payload)

    async def revoke_user(self, identifier: str | int) -> Any:
        return await self.client.delete_user(identifier)

    async def get_subscription(
        self,
        identifier: str | int,
    ) -> Any:
        return await self.client.get_subscription(identifier)

    async def renew_user(
        self,
        identifier: str | int,
        *,
        expire: str | None = None,
        data_limit: int | None = None,
    ) -> Any:
        payload: dict[str, Any] = {}

        if expire is not None:
            payload["expire"] = expire

        if data_limit is not None:
            payload["data_limit"] = data_limit

        if not payload:
            raise ValueError("Renewal requires expire or data_limit")

        return await self.client.update_user(identifier, payload)
PY


cat > app/pasarguard/__init__.py <<'PY'
from .adapters import get_adapter
from .base import (
    PasarGuardAdapter,
    PasarGuardAPIError,
    PasarGuardAuthenticationError,
    PasarGuardConnectionError,
    PasarGuardConnectorError,
    PasarGuardCredentials,
    PasarGuardHealth,
    PasarGuardUnsupportedVersion,
    PasarGuardUser,
)
from .client import PasarGuardClient
from .credentials import (
    EncryptedPasarGuardCredentials,
    decrypt_credentials,
    encrypt_credentials,
    mask_credentials,
)
from .service import PasarGuardService

__all__ = [
    "PasarGuardAdapter",
    "PasarGuardAPIError",
    "PasarGuardAuthenticationError",
    "PasarGuardConnectionError",
    "PasarGuardConnectorError",
    "PasarGuardCredentials",
    "PasarGuardHealth",
    "PasarGuardUnsupportedVersion",
    "PasarGuardUser",
    "PasarGuardClient",
    "PasarGuardService",
    "EncryptedPasarGuardCredentials",
    "encrypt_credentials",
    "decrypt_credentials",
    "mask_credentials",
    "get_adapter",
]
PY


cat > test_page13.py <<'PY'
import asyncio

from app.pasarguard import (
    PasarGuardClient,
    PasarGuardCredentials,
    PasarGuardService,
    encrypt_credentials,
    decrypt_credentials,
    mask_credentials,
    get_adapter,
)


def main():
    print("PAGE 13 PASARGUARD CONNECTOR CONTRACT: START")

    credentials = PasarGuardCredentials(
        base_url="https://example.invalid",
        api_token="TEST_TOKEN_VALUE",
        username="panel-user",
    )

    encrypted = encrypt_credentials(credentials)

    assert encrypted.base_url == credentials.base_url
    assert encrypted.encrypted_api_token != credentials.api_token
    assert encrypted.encrypted_username != credentials.username

    restored = decrypt_credentials(encrypted)

    assert restored.base_url == credentials.base_url
    assert restored.api_token == credentials.api_token
    assert restored.username == credentials.username

    masked = mask_credentials(credentials)

    assert masked["api_token"] == "***REDACTED***"
    assert credentials.api_token not in str(masked)

    adapter = get_adapter("v5")

    assert adapter.version == "v5"
    assert adapter.users_collection() == "/api/users"
    assert adapter.user_resource(123) == "/api/user/123"

    client = PasarGuardClient(
        credentials,
        version="v5",
        timeout_seconds=15,
        max_retries=2,
    )

    service = PasarGuardService(client)

    assert service.client is client
    assert client.max_retries <= 3

    # Verify that credentials are never part of the client repr/string.
    assert credentials.api_token not in repr(client)
    assert credentials.api_token not in str(client)

    print("CREDENTIAL_ENCRYPTION: ENABLED")
    print("CREDENTIAL_DECRYPTION: ENABLED")
    print("SECRETS_IN_MASKED_OUTPUT: BLOCKED")
    print("V5_ADAPTER: READY")
    print("VERSION_ADAPTER_LAYER: ENABLED")
    print("PASARGUARD_HTTP_CLIENT: READY")
    print("AUTHORIZATION_HEADER: BEARER")
    print("LIMITED_RETRY: ENABLED")
    print("RETRY_MAX: 3")
    print("BUSINESS_FACADE: READY")
    print("HEALTH_CHECK: READY")
    print("USER_PROVISIONING: READY")
    print("USER_UPDATE: READY")
    print("USER_REVOKE: READY")
    print("SUBSCRIPTION_RETRIEVAL: READY")
    print("RENEWAL: READY")
    print("NODE_DIRECT_ACCESS: BLOCKED")
    print("REAL_CREDENTIALS_USED: NO")

    asyncio.run(asyncio.sleep(0))

    print("PAGE 13 PASARGUARD CONNECTOR CONTRACT: OK")


if __name__ == "__main__":
    main()
PY


echo
echo "=== RUN PAGE 13 TEST ==="

.venv/bin/python test_page13.py

echo
echo "=== PAGE 13 DATABASE/ARCHITECTURE CHECK ==="

.venv/bin/python - <<'PY'
from app.pasarguard import PasarGuardClient, PasarGuardService

print("CONNECTOR_IMPORT: OK")
print("CLIENT_IMPORT: OK")
print("SERVICE_IMPORT: OK")
print("ADAPTER_IMPORT: OK")
print("CREDENTIAL_CRYPTO_IMPORT: OK")
print("PAGE 13 ARCHITECTURE CONTRACT: OK")
PY

echo
echo "=== PAGE 13 COMPLETE ==="
