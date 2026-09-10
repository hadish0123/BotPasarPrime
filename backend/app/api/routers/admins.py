from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Admin, AdminRole, Permission, Role, RolePermission, TenantUserRole, User
from app.security.rbac import ROLE_PERMISSIONS

r = APIRouter(prefix="/admins", tags=["admins"])


class AdminCreate(BaseModel):
    telegram_id: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=100)
    role: str = Field(min_length=2, max_length=50)
    tenant_id: int | None = Field(default=None, gt=0)


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    tenant_id: int | None = Field(default=None, gt=0)
    permissions: list[str] = Field(default_factory=list, max_length=100)


def _tenant_allowed(tenant_id: int | None, claims: dict) -> bool:
    if tenant_id is None:
        if claims.get("role") != "Owner":
            raise HTTPException(403, "platform_owner_required")
        return True
    require_tenant_match(tenant_id, claims)
    return True


@r.get("")
async def list_admins(claims=Depends(require_permission("admins.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin, User).join(User, User.id == Admin.user_id).order_by(Admin.id.desc()))
    rows = []
    for admin, user in result.all():
        roles_query = (
            select(Role.name, AdminRole.tenant_id)
            .join(AdminRole, AdminRole.role_id == Role.id)
            .where(AdminRole.admin_id == admin.id)
        )
        if claims.get("role") != "Owner":
            tenant_id = claims.get("tenant_id")
            if tenant_id is None:
                continue
            roles_query = roles_query.where(AdminRole.tenant_id == tenant_id)
        role_rows = (await db.execute(roles_query)).all()
        if claims.get("role") != "Owner" and not role_rows:
            continue
        rows.append({
            "id": admin.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "is_active": admin.active,
            "roles": [{"name": name, "tenant_id": tenant} for name, tenant in role_rows],
        })
    return rows


@r.post("")
async def create_admin(x: AdminCreate, claims=Depends(require_permission("admins.write")), db: AsyncSession = Depends(get_db)):
    _tenant_allowed(x.tenant_id, claims)
    role = None
    if x.tenant_id is not None:
        role = await db.scalar(
            select(Role).where(Role.name == x.role, Role.tenant_id == x.tenant_id)
        )
    if role is None:
        role = await db.scalar(
            select(Role).where(Role.name == x.role, Role.tenant_id.is_(None))
        )
    if role is None:
        raise HTTPException(400, "role_not_found")

    user = await db.scalar(select(User).where(User.telegram_id == x.telegram_id))
    if user is None:
        user = User(telegram_id=x.telegram_id, username=x.username)
        db.add(user)
        await db.flush()
    elif x.username is not None:
        user.username = x.username

    admin = await db.scalar(select(Admin).where(Admin.user_id == user.id))
    if admin is None:
        admin = Admin(user_id=user.id, active=True)
        db.add(admin)
        await db.flush()
    else:
        admin.active = True

    existing = await db.scalar(
        select(AdminRole).where(
            AdminRole.admin_id == admin.id,
            AdminRole.role_id == role.id,
            AdminRole.tenant_id == x.tenant_id,
        )
    )
    if existing is None:
        db.add(AdminRole(admin_id=admin.id, role_id=role.id, tenant_id=x.tenant_id))

    if x.tenant_id is not None:
        membership = await db.scalar(
            select(TenantUserRole).where(
                TenantUserRole.tenant_id == x.tenant_id,
                TenantUserRole.user_id == user.id,
                TenantUserRole.role_id == role.id,
            )
        )
        if membership is None:
            db.add(TenantUserRole(tenant_id=x.tenant_id, user_id=user.id, role_id=role.id))
    await db.commit()
    return {"id": admin.id, "telegram_id": user.telegram_id, "role": role.name, "tenant_id": x.tenant_id}


@r.get("/roles")
async def list_roles(claims=Depends(require_permission("admins.read")), db: AsyncSession = Depends(get_db)):
    query = select(Role).order_by(Role.name)
    if claims.get("role") != "Owner":
        tenant_id = claims.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(403, "tenant_context_required")
        query = query.where((Role.tenant_id == tenant_id) | (Role.tenant_id.is_(None)))
    result = await db.execute(query)
    return [
        {
            "id": role.id,
            "tenant_id": role.tenant_id,
            "name": role.name,
            "description": role.description,
            "is_system": bool(role.is_system or role.name in ROLE_PERMISSIONS),
        }
        for role in result.scalars().all()
    ]


@r.post("/roles")
async def create_role(x: RoleCreate, claims=Depends(require_permission("admins.write")), db: AsyncSession = Depends(get_db)):
    _tenant_allowed(x.tenant_id, claims)
    if x.name in ROLE_PERMISSIONS:
        raise HTTPException(400, "system_role_name_reserved")
    if x.tenant_id is None and claims.get("role") != "Owner":
        raise HTTPException(403, "platform_owner_required")
    duplicate_query = select(Role).where(Role.name == x.name)
    if x.tenant_id is None:
        duplicate_query = duplicate_query.where(Role.tenant_id.is_(None))
    else:
        duplicate_query = duplicate_query.where(Role.tenant_id == x.tenant_id)
    duplicate = await db.scalar(duplicate_query)
    if duplicate is not None:
        raise HTTPException(409, "role_exists")
    role = Role(name=x.name, description=x.description, tenant_id=x.tenant_id, is_system=False)
    db.add(role)
    await db.flush()
    if x.permissions:
        perms = (await db.scalars(select(Permission).where(Permission.key.in_(x.permissions)))).all()
        if len(perms) != len(set(x.permissions)):
            await db.rollback()
            raise HTTPException(400, "unknown_permission")
        for permission in perms:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.commit()
    return {"id": role.id, "tenant_id": role.tenant_id, "name": role.name, "permissions": x.permissions}
