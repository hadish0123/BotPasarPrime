from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import Tenant, TenantUser, User
from app.security.jwt import create_token
from app.security.telegram_init_data import validate_init_data

r = APIRouter(prefix="/auth", tags=["auth"])


async def _telegram_user(payload: str) -> tuple[int, dict]:
    ok, data = validate_init_data(
        payload,
        settings.telegram_bot_token or settings.central_bot_token,
        max_age=settings.telegram_init_data_max_age,
    )
    if not ok:
        raise HTTPException(401, "invalid Telegram initData")
    raw_user = data.get("user")
    if not isinstance(raw_user, dict) or not raw_user.get("id"):
        raise HTTPException(401, "Telegram user identity missing")
    return int(raw_user["id"]), raw_user


@r.post("/telegram")
async def telegram_auth(
    init_data: str | None = None,
    x_telegram_init_data: str | None = Header(default=None),
):
    payload = x_telegram_init_data or init_data
    if not payload:
        raise HTTPException(400, "Telegram initData is required")
    telegram_id, raw_user = await _telegram_user(payload)
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=raw_user.get("username"),
                first_name=raw_user.get("first_name"),
            )
            db.add(user)
            await db.flush()
        else:
            user.username = raw_user.get("username")
            user.first_name = raw_user.get("first_name")
        user_id = int(user.id)
        await db.commit()

    claims = {
        "telegram_id": telegram_id,
        "user_id": user_id,
        "username": raw_user.get("username"),
        "tenant_id": None,
        "permissions": ["auth.telegram"],
    }
    return {
        "access_token": create_token(user_id, claims),
        "token_type": "bearer",
    }


@r.post("/telegram/{tenant_id}")
async def tenant_telegram_auth(
    tenant_id: int,
    init_data: str | None = None,
    x_telegram_init_data: str | None = Header(default=None),
):
    payload = x_telegram_init_data or init_data
    if not payload:
        raise HTTPException(400, "Telegram initData is required")
    telegram_id, _ = await _telegram_user(payload)

    async with SessionLocal() as db:
        tenant = await db.scalar(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.is_deleted.is_(False),
                Tenant.status == "active",
            )
        )
        user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
        if not tenant or not user:
            raise HTTPException(403, "tenant access denied")
        membership = await db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.user_id == user.id,
                TenantUser.status == "active",
            )
        )
        if not membership:
            raise HTTPException(403, "tenant access denied")

        permissions = [
            "auth.telegram",
            "users.read",
            "products.read",
            "orders.read",
            "orders.write",
            "payments.write",
            "services.read",
            "tickets.write",
        ]
        claims = {
            "telegram_id": telegram_id,
            "user_id": int(user.id),
            "tenant_id": tenant_id,
            "role": membership.role,
            "permissions": permissions,
        }
        return {
            "access_token": create_token(int(user.id), claims),
            "token_type": "bearer",
            "tenant_id": tenant_id,
        }
