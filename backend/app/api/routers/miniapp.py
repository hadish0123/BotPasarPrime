from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.security.telegram_init_data import validate_init_data

r = APIRouter(prefix="/miniapp", tags=["miniapp"])


@r.post("/validate")
async def validate(init_data: str):
    ok, data = validate_init_data(init_data, settings.telegram_bot_token)
    if not ok:
        raise HTTPException(401, "invalid initData")
    return {"valid": True, "data": data}
