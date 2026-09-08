from fastapi import APIRouter

r = APIRouter(prefix="/users", tags=["users"])


@r.get("")
async def users(tenant_id: int):
    return {"tenant_id": tenant_id, "items": []}
