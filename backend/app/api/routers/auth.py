from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select

from app.api.deps import bearer
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import Permission, Role, RolePermission, Tenant, TenantUser, User
from app.security.jwt import create_token
from app.security.rbac import permissions_for_role
from app.security.telegram_init_data import validate_init_data

r = APIRouter(prefix="/auth", tags=["auth"])


async def _telegram_user(payload: str) -> tuple[int, dict]:
    token = settings.telegram_bot_token or settings.central_bot_token
    if not token:
        raise HTTPException(503, "Telegram authentication is not configured")
    ok, data = validate_init_data(payload, token, max_age=settings.telegram_init_data_max_age)
    if not ok:
        raise HTTPException(401, "invalid Telegram initData")
    raw_user = data.get("user")
    if not isinstance(raw_user, dict) or not raw_user.get("id"):
        raise HTTPException(401, "Telegram user identity missing")
    return int(raw_user["id"]), raw_user


async def _upsert_user(telegram_id: int, raw_user: dict) -> int:
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
    return user_id


async def _tenant_permissions(db, tenant_id: int, user_id: int, fallback_role: str) -> set[str]:
    role_names = {fallback_role} if fallback_role else set()
    membership = await db.scalar(select(TenantUser).where(TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id, TenantUser.status == "active"))
    if membership and membership.role:
        role_names.add(membership.role)
    permissions: set[str] = set()
    for role_name in role_names:
        permissions.update(permissions_for_role(role_name))
    custom_rows = await db.execute(select(Permission.key).join(RolePermission, RolePermission.permission_id == Permission.id).join(Role, Role.id == RolePermission.role_id).join(TenantUser, TenantUser.user_id == user_id).where(TenantUser.tenant_id == tenant_id, TenantUser.status == "active", Role.tenant_id == tenant_id))
    permissions.update(row[0] for row in custom_rows.all())
    return permissions


@r.post("/telegram")
async def telegram_auth(init_data: str | None = None, x_telegram_init_data: str | None = Header(default=None)):
    payload = x_telegram_init_data or init_data
    if not payload:
        raise HTTPException(400, "Telegram initData is required")
    telegram_id, raw_user = await _telegram_user(payload)
    user_id = await _upsert_user(telegram_id, raw_user)
    return {"access_token": create_token(user_id, {"telegram_id": telegram_id, "user_id": user_id, "username": raw_user.get("username"), "tenant_id": None, "permissions": ["auth.telegram"]}), "token_type": "bearer"}


@r.post("/telegram/{tenant_id}")
async def tenant_telegram_auth(tenant_id: int, init_data: str | None = None, x_telegram_init_data: str | None = Header(default=None)):
    payload = x_telegram_init_data or init_data
    if not payload:
        raise HTTPException(400, "Telegram initData is required")
    telegram_id, raw_user = await _telegram_user(payload)
    user_id = await _upsert_user(telegram_id, raw_user)

    async with SessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted.is_(False), Tenant.status == "active"))
        if not tenant:
            raise HTTPException(403, "tenant access denied")
        membership = await db.scalar(select(TenantUser).where(TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id, TenantUser.status == "active"))
        if membership is None:
            membership = TenantUser(tenant_id=tenant_id, user_id=user_id, status="active", role="customer")
            db.add(membership)
            await db.flush()
        permissions = await _tenant_permissions(db, tenant_id, user_id, membership.role)
        claims = {"telegram_id": telegram_id, "user_id": user_id, "tenant_id": tenant_id, "role": membership.role, "permissions": sorted(permissions | {"auth.telegram"})}
        return {"access_token": create_token(user_id, claims), "token_type": "bearer", "tenant_id": tenant_id}


@r.get("/me")
async def me(claims=Depends(bearer)):
    return {"user_id": claims.get("user_id") or claims.get("sub"), "telegram_id": claims.get("telegram_id"), "username": claims.get("username"), "tenant_id": claims.get("tenant_id"), "role": claims.get("role"), "permissions": claims.get("permissions", []), "is_platform_owner": bool(claims.get("is_platform_owner"))}
