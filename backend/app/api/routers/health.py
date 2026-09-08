from fastapi import APIRouter

r = APIRouter(tags=["system"])


@r.get("/health")
async def health():
    return {"status": "ok", "service": "3XSHOP"}
