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
    """Thin transport layer with bounded, safe retries and no secret logging."""

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
        retryable = method in {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}
        attempts = 1 + (self.max_retries if retryable else 0)
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=self._headers()) as session:
                    async with session.request(method, url, json=json, params=params) as response:
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
                        if "application/json" in response.headers.get("Content-Type", ""):
                            return await response.json()
                        return body_text
            except PasarGuardAuthenticationError:
                raise
            except PasarGuardAPIError as exc:
                if not (500 <= _status_from_error(str(exc)) <= 599):
                    raise
                last_error = exc
            except (TimeoutError, aiohttp.ClientError) as exc:
                last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))

        raise PasarGuardConnectionError("Unable to communicate with PasarGuard") from last_error

    async def health(self) -> PasarGuardHealth:
        started = time.monotonic()
        try:
            await self.request("GET", "/")
            return PasarGuardHealth(ok=True, version=self.adapter.version, latency_ms=round((time.monotonic() - started) * 1000, 2))
        except Exception as exc:  # noqa: BLE001
            return PasarGuardHealth(ok=False, version=self.adapter.version, latency_ms=round((time.monotonic() - started) * 1000, 2), detail=type(exc).__name__)

    async def list_users(self, *, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", self.adapter.users_collection(), params=params)

    async def get_user(self, identifier: str | int) -> Any:
        return await self.request("GET", self.adapter.user_resource(identifier))

    async def create_user(self, payload: dict[str, Any]) -> Any:
        return await self.request("POST", self.adapter.users_collection().replace("/users", "/user"), json=self.adapter.build_create_user_payload(payload))

    async def update_user(self, identifier: str | int, payload: dict[str, Any]) -> Any:
        return await self.request("PUT", self.adapter.user_resource(identifier), json=self.adapter.build_update_user_payload(payload))

    async def delete_user(self, identifier: str | int) -> Any:
        return await self.request("DELETE", self.adapter.user_resource(identifier))

    async def get_subscription(self, identifier: str | int) -> Any:
        return await self.request("GET", self.adapter.user_subscription(identifier))

    async def renew_subscription(self, identifier: str | int, *, expire: int, data_limit: int | None = None) -> Any:
        payload: dict[str, Any] = {"expire": expire}
        if data_limit is not None:
            payload["data_limit"] = data_limit
        return await self.update_user(identifier, payload)


def _status_from_error(message: str) -> int:
    marker = "PasarGuard API error "
    if marker not in message:
        return 0
    try:
        return int(message.split(marker, 1)[1].split(":", 1)[0])
    except (ValueError, IndexError):
        return 0
