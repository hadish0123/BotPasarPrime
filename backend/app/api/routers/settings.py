from fastapi import APIRouter

r = APIRouter(prefix="/settings", tags=["settings"])


@r.get("")
async def settings(tenant_id: int):
    return {"tenant_id": tenant_id, "activation_fee_toman": 250000}
