from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    Permission,
    Role,
    RolePermission,
    TenantUserRole,
)

DEFAULT_ROLES = (
    "Owner",
    "Admin",
    "Finance",
    "Support",
    "Sales",
    "Viewer",
)


DEFAULT_PERMISSIONS = (
    "users.read",
    "users.write",
    "orders.read",
    "orders.write",
    "payments.read",
    "payments.verify",
    "products.read",
    "products.write",
    "wallet.read",
    "wallet.write",
    "coupons.read",
    "coupons.write",
    "referrals.read",
    "referrals.write",
    "tickets.read",
    "tickets.write",
    "settings.read",
    "settings.write",
    "admins.read",
    "admins.manage",
    "reports.read",
    "audit.read",
)


ROLE_PERMISSIONS = {
    "Owner": set(DEFAULT_PERMISSIONS),
    "Admin": set(DEFAULT_PERMISSIONS)
    - {
        "admins.manage",
    },
    "Finance": {
        "orders.read",
        "payments.read",
        "payments.verify",
        "wallet.read",
        "wallet.write",
        "reports.read",
    },
    "Support": {
        "users.read",
        "orders.read",
        "tickets.read",
        "tickets.write",
    },
    "Sales": {
        "users.read",
        "orders.read",
        "products.read",
        "products.write",
        "coupons.read",
        "coupons.write",
        "referrals.read",
    },
    "Viewer": {
        "users.read",
        "orders.read",
        "payments.read",
        "products.read",
        "wallet.read",
        "coupons.read",
        "referrals.read",
        "tickets.read",
        "settings.read",
        "reports.read",
        "audit.read",
    },
}


@dataclass(frozen=True)
class RBACContext:
    tenant_id: int
    user_id: int


class RBACError(Exception):
    pass


class MissingTenantContextError(RBACError):
    pass


class CrossTenantAccessError(RBACError):
    pass


class PermissionDeniedError(RBACError):
    pass


def require_same_tenant(
    tenant_id: int,
    requested_tenant_id: int,
):
    if tenant_id != requested_tenant_id:
        raise CrossTenantAccessError("cross_tenant_access_blocked")


async def get_user_roles(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
):
    rows = await db.scalars(
        select(TenantUserRole).where(
            TenantUserRole.tenant_id == tenant_id,
            TenantUserRole.user_id == user_id,
        )
    )

    return list(rows.all())


async def has_permission(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
    permission_key: str,
) -> bool:
    require_permission_key(permission_key)

    roles = await get_user_roles(
        db,
        tenant_id,
        user_id,
    )

    if not roles:
        return False

    role_ids = [row.role_id for row in roles]

    permissions = await db.scalars(
        select(Permission)
        .join(
            RolePermission,
            RolePermission.permission_id == Permission.id,
        )
        .where(
            RolePermission.role_id.in_(role_ids),
            Permission.key == permission_key,
        )
    )

    return permissions.first() is not None


async def require_permission(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
    permission_key: str,
):
    if not await has_permission(
        db,
        tenant_id,
        user_id,
        permission_key,
    ):
        raise PermissionDeniedError(permission_key)


def require_permission_key(
    permission_key: str,
):
    if not permission_key or "." not in permission_key or len(permission_key) > 100:
        raise ValueError("invalid_permission_key")

    allowed = set(DEFAULT_PERMISSIONS)

    if permission_key not in allowed:
        raise ValueError("unknown_permission_key")


async def create_role(
    db: AsyncSession,
    tenant_id: int,
    name: str,
    description: str | None = None,
):
    name = name.strip()

    if name not in DEFAULT_ROLES:
        if not name:
            raise ValueError("invalid_role_name")

    existing = await db.scalar(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.name == name,
        )
    )

    if existing:
        return existing

    role = Role(
        tenant_id=tenant_id,
        name=name,
        description=description,
        is_system=name in DEFAULT_ROLES,
    )

    db.add(role)
    await db.flush()

    return role


async def ensure_permissions(
    db: AsyncSession,
):
    for key in DEFAULT_PERMISSIONS:
        existing = await db.scalar(select(Permission).where(Permission.key == key))

        if not existing:
            db.add(
                Permission(
                    key=key,
                    description=key,
                )
            )

    await db.flush()


async def ensure_default_roles(
    db: AsyncSession,
    tenant_id: int,
):
    await ensure_permissions(db)

    permissions = {row.key: row for row in (await db.scalars(select(Permission))).all()}

    result = {}

    for role_name in DEFAULT_ROLES:
        role = await create_role(
            db,
            tenant_id,
            role_name,
        )

        wanted = ROLE_PERMISSIONS[role_name]

        for key in wanted:
            permission = permissions[key]

            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permission.id,
                )
            )

            if not exists:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )

        result[role_name] = role

    await db.flush()

    return result


async def assign_role(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
    role_id: int,
):
    role = await db.scalar(
        select(Role).where(
            Role.id == role_id,
            Role.tenant_id == tenant_id,
        )
    )

    if not role:
        raise CrossTenantAccessError("role_not_in_tenant")

    existing = await db.scalar(
        select(TenantUserRole).where(
            TenantUserRole.tenant_id == tenant_id,
            TenantUserRole.user_id == user_id,
            TenantUserRole.role_id == role_id,
        )
    )

    if existing:
        return existing

    assignment = TenantUserRole(
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role_id,
    )

    db.add(assignment)
    await db.flush()

    return assignment


async def assign_owner(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
):
    roles = await ensure_default_roles(
        db,
        tenant_id,
    )

    return await assign_role(
        db,
        tenant_id,
        user_id,
        roles["Owner"].id,
    )
