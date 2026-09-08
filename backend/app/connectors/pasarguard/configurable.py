import httpx


class ConfigurablePasarGuard:
    def __init__(self, base_url, token, mappings=None, timeout=15):
        self.base = base_url.rstrip("/")
        self.token = token
        self.mappings = mappings or {}
        self.timeout = timeout

    def url(self, op):
        path = self.mappings.get(op)
        if not path:
            raise RuntimeError(f"PasarGuard mapping missing: {op}")
        return self.base + "/" + path.lstrip("/")

    async def request(self, op, method="GET", json=None):
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.request(
                method, self.url(op), headers={"Authorization": f"Bearer {self.token}"}, json=json
            )
            r.raise_for_status()
            return r.json()

    async def authenticate(self):
        return await self.request("authenticate", "GET")

    async def fetch_resources(self):
        return await self.request("fetch_resources")

    async def create_service(self, payload):
        return await self.request("create_service", "POST", payload)

    async def update_service(self, eid, payload):
        return await self.request("update_service", "PATCH", payload)

    async def service_status(self, eid):
        return await self.request("service_status")

    async def renew_service(self, eid, payload):
        return await self.request("renew_service", "POST", payload)
