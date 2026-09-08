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
