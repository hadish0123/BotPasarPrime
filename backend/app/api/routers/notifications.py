from fastapi import APIRouter

r = APIRouter(prefix="/notifications", tags=["notifications"])


@r.get("")
async def notifications(tenant_id: int, user_id: int):
    return {"tenant_id": tenant_id, "user_id": user_id, "items": []}
