from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.security.jwt import create_token
from app.security.telegram_init_data import validate_init_data

r = APIRouter(prefix="/auth", tags=["auth"])


@r.post("/telegram")
async def telegram_auth(init_data: str):
    ok, data = validate_init_data(init_data, settings.telegram_bot_token)
    if not ok:
        raise HTTPException(401, "invalid Telegram initData")
    return {"access_token": create_token(data.get("user", "unknown")), "token_type": "bearer"}
