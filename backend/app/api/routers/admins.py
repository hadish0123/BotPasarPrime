from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.deps import require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import Admin, AdminRole, Permission, Role, RolePermission
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


@r.get("")
async def list_admins(claims=Depends(require_permission("admins.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).order_by(Admin.id.desc()))
    rows = []
    for admin in result.scalars().all():
        roles = await db.execute(select(Role.name, AdminRole.tenant_id).join(AdminRole, AdminRole.role_id == Role.id).where(AdminRole.admin_id == admin.id))
        rows.append({"id": admin.id, "telegram_id": admin.telegram_id, "username": admin.username, "is_active": admin.is_active, "roles": [{"name": name, "tenant_id": tenant} for name, tenant in roles.all()]})
    return rows


@r.post("")
async def create_admin(x: AdminCreate, claims=Depends(require_permission("admins.write")), db: AsyncSession = Depends(get_db)):
    if x.tenant_id is not None:
        require_tenant_match(x.tenant_id, claims)
    if x.role not in ROLE_PERMISSIONS:
        role = await db.scalar(select(Role).where(Role.name == x.role, Role.tenant_id == x.tenant_id))
        if role is None:
            raise HTTPException(400, "role_not_found")
    else:
        role = await db.scalar(select(Role).where(Role.name == x.role, Role.tenant_id.is_(None)))
    admin = await db.scalar(select(Admin).where(Admin.telegram_id == x.telegram_id))
    if admin is None:
        admin = Admin(telegram_id=x.telegram_id, username=x.username, is_active=True)
        db.add(admin)
        await db.flush()
    elif not admin.is_active:
        admin.is_active = True
        admin.username = x.username
    if role is None:
        raise HTTPException(400, "role_not_found")
    existing = await db.scalar(select(AdminRole).where(AdminRole.admin_id == admin.id, AdminRole.role_id == role.id, AdminRole.tenant_id == x.tenant_id))
    if existing is None:
        db.add(AdminRole(admin_id=admin.id, role_id=role.id, tenant_id=x.tenant_id))
    await db.commit()
    return {"id": admin.id, "telegram_id": admin.telegram_id, "role": role.name, "tenant_id": x.tenant_id}


@r.get("/roles")
async def list_roles(claims=Depends(require_permission("admins.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Role).order_by(Role.tenant_id, Role.name))
    return [{"id": r.id, "tenant_id": r.tenant_id, "name": r.name, "description": r.description, "is_system": r.is_system} for r in result.scalars().all()]


@r.post("/roles")
async def create_role(x: RoleCreate, claims=Depends(require_permission("admins.write")), db: AsyncSession = Depends(get_db)):
    if x.tenant_id is not None:
        require_tenant_match(x.tenant_id, claims)
    if x.name in ROLE_PERMISSIONS:
        raise HTTPException(400, "system_role_name_reserved")
    role = Role(tenant_id=x.tenant_id, name=x.name, description=x.description, is_system=False)
    db.add(role)
    await db.flush()
    if x.permissions:
        perms = (await db.scalars(select(Permission).where(Permission.key.in_(x.permissions)))).all()
        if len(perms) != len(set(x.permissions)):
            raise HTTPException(400, "unknown_permission")
        for permission in perms:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.commit()
    return {"id": role.id, "tenant_id": role.tenant_id, "name": role.name, "permissions": x.permissions}
