from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import User
from app.security.jwt import create_token
from app.security.telegram_init_data import validate_init_data

r = APIRouter(prefix="/auth", tags=["auth"])


@r.post("/telegram")
async def telegram_auth(init_data: str | None = None, x_telegram_init_data: str | None = Header(default=None)):
    payload = x_telegram_init_data or init_data
    if not payload:
        raise HTTPException(400, "Telegram initData is required")
    ok, data = validate_init_data(payload, settings.telegram_bot_token or settings.central_bot_token, max_age=settings.telegram_init_data_max_age)
    if not ok:
        raise HTTPException(401, "invalid Telegram initData")
    raw_user = data.get("user")
    if not isinstance(raw_user, dict) or not raw_user.get("id"):
        raise HTTPException(401, "Telegram user identity missing")
    telegram_id = int(raw_user["id"])
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(telegram_id=telegram_id, username=raw_user.get("username"), first_name=raw_user.get("first_name"))
            db.add(user)
            await db.flush()
        else:
            user.username = raw_user.get("username")
            user.first_name = raw_user.get("first_name")
        user_id = int(user.id)
        await db.commit()
    claims = {"telegram_id": telegram_id, "user_id": user_id, "username": raw_user.get("username"), "tenant_id": None, "permissions": ["auth.telegram"]}
    return {"access_token": create_token(user_id, claims), "token_type": "bearer"}
