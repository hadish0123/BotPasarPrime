from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.tenant_isolation import CrossTenantAccessError
from app.models.entities import (
    Role,
)
from app.rbac import (
    DEFAULT_PERMISSIONS,
    assign_role,
    ensure_default_roles,
    has_permission,
    require_same_tenant,
)

router = APIRouter(
    prefix="/rbac",
    tags=["rbac"],
)


@router.get("/permissions")
async def permissions():
    return {"permissions": list(DEFAULT_PERMISSIONS)}


@router.get("/roles")
async def roles(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(Role).where(Role.tenant_id == tenant_id))

    return [
        {
            "id": role.id,
            "tenant_id": role.tenant_id,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
        }
        for role in rows.all()
    ]


@router.post("/initialize")
async def initialize(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        roles = await ensure_default_roles(
            db,
            tenant_id,
        )
        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return {
        "tenant_id": tenant_id,
        "roles": {name: role.id for name, role in roles.items()},
    }


@router.post("/assign")
async def assign(
    tenant_id: int,
    user_id: int,
    role_id: int,
    requested_tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    if requested_tenant_id is not None:
        try:
            require_same_tenant(
                tenant_id,
                requested_tenant_id,
            )
        except CrossTenantAccessError as exc:
            raise HTTPException(
                status_code=403,
                detail=str(exc),
            ) from exc

    try:
        assignment = await assign_role(
            db,
            tenant_id,
            user_id,
            role_id,
        )
        await db.commit()

    except Exception as exc:  # noqa: BLE001 - rollback boundary protects transaction integrity
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None

    return {
        "id": assignment.id,
        "tenant_id": assignment.tenant_id,
        "user_id": assignment.user_id,
        "role_id": assignment.role_id,
    }


@router.get("/check")
async def check(
    tenant_id: int,
    user_id: int,
    permission: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        allowed = await has_permission(
            db,
            tenant_id,
            user_id,
            permission,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "permission": permission,
        "allowed": allowed,
    }
