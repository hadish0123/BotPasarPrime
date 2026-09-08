from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExternalService:
    external_id: str
    status: str
    expires_at: str | None = None
    metadata: dict | None = None


class PasarGuardConnector(ABC):
    @abstractmethod
    async def authenticate(self): ...
    @abstractmethod
    async def fetch_resources(self): ...
    @abstractmethod
    async def create_service(self, payload): ...
    @abstractmethod
    async def update_service(self, external_id, payload): ...
    @abstractmethod
    async def service_status(self, external_id): ...
    @abstractmethod
    async def renew_service(self, external_id, payload): ...
