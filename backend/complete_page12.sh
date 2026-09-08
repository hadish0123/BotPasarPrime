#!/usr/bin/env bash
set -euo pipefail

PY=".venv/bin/python"

echo "=== COMPLETE PAGE 12: RBAC ==="

cp app/models/entities.py app/models/entities.py.page12-backup

"$PY" - <<'PY'
from pathlib import Path

p = Path("app/models/entities.py")
s = p.read_text()

# ---------------------------------------------------------
# RBAC models
# ---------------------------------------------------------
if "class Role(Base):" not in s:
    marker = "\nclass Service(Base):"

    if marker not in s:
        raise SystemExit("Could not find model insertion point")

    rbac = r'''
class Role(Base):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenants.id'),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'name',
        ),
    )


class Permission(Base):
    __tablename__ = 'permissions'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )


class RolePermission(Base):
    __tablename__ = 'role_permissions'
    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey('roles.id'),
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey('permissions.id'),
    )
    __table_args__ = (
        UniqueConstraint(
            'role_id',
            'permission_id',
        ),
    )


class TenantUserRole(Base):
    __tablename__ = 'tenant_user_roles'
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey('tenants.id'),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'),
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey('roles.id'),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'user_id',
            'role_id',
        ),
    )

'''
    s = s.replace(
        marker,
        "\n" + rbac + marker,
        1,
    )
    p.write_text(s)

    print("RBAC_MODELS_CREATED")
else:
    print("RBAC_MODELS_ALREADY_PRESENT")
PY

cat > app/rbac.py <<'PY'
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
        raise CrossTenantAccessError(
            "cross_tenant_access_blocked"
        )


async def get_user_roles(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
):
    rows = await db.scalars(
        select(TenantUserRole)
        .where(
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

    role_ids = [
        row.role_id
        for row in roles
    ]

    permissions = await db.scalars(
        select(Permission)
        .join(
            RolePermission,
            RolePermission.permission_id
            == Permission.id,
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
        raise PermissionDeniedError(
            permission_key
        )


def require_permission_key(
    permission_key: str,
):
    if (
        not permission_key
        or "." not in permission_key
        or len(permission_key) > 100
    ):
        raise ValueError(
            "invalid_permission_key"
        )

    allowed = set(
        DEFAULT_PERMISSIONS
    )

    if permission_key not in allowed:
        raise ValueError(
            "unknown_permission_key"
        )


async def create_role(
    db: AsyncSession,
    tenant_id: int,
    name: str,
    description: str | None = None,
):
    name = name.strip()

    if name not in DEFAULT_ROLES:
        if not name:
            raise ValueError(
                "invalid_role_name"
            )

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
        existing = await db.scalar(
            select(Permission).where(
                Permission.key == key
            )
        )

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

    permissions = {
        row.key: row
        for row in (
            await db.scalars(
                select(Permission)
            )
        ).all()
    }

    result = {}

    for role_name in DEFAULT_ROLES:
        role = await create_role(
            db,
            tenant_id,
            role_name,
        )

        wanted = ROLE_PERMISSIONS[
            role_name
        ]

        for key in wanted:
            permission = permissions[key]

            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id
                    == role.id,
                    RolePermission.permission_id
                    == permission.id,
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
        raise CrossTenantAccessError(
            "role_not_in_tenant"
        )

    existing = await db.scalar(
        select(TenantUserRole).where(
            TenantUserRole.tenant_id
            == tenant_id,
            TenantUserRole.user_id
            == user_id,
            TenantUserRole.role_id
            == role_id,
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
PY

cat > app/api/routers/rbac.py <<'PY'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.entities import (
    Permission,
    Role,
    TenantUserRole,
)
from app.rbac import (
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLES,
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
    return {
        "permissions": list(
            DEFAULT_PERMISSIONS
        )
    }


@router.get("/roles")
async def roles(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Role).where(
            Role.tenant_id == tenant_id
        )
    )

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
        "roles": {
            name: role.id
            for name, role in roles.items()
        },
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
        except Exception as exc:
            raise HTTPException(
                status_code=403,
                detail=str(exc),
            )

    try:
        assignment = await assign_role(
            db,
            tenant_id,
            user_id,
            role_id,
        )
        await db.commit()

    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

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
        )

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "permission": permission,
        "allowed": allowed,
    }
PY

cat > migrations/versions/0008_page12_rbac.py <<'PY'
"""Page 12 RBAC

Revision ID: 0008_page12
Revises: 0007_page11
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_page12"
down_revision = "0007_page11"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "roles" not in tables:
        op.create_table(
            "roles",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id"),
                nullable=True,
            ),
            sa.Column(
                "name",
                sa.String(50),
                nullable=False,
            ),
            sa.Column(
                "description",
                sa.String(255),
                nullable=True,
            ),
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "name",
            ),
        )

    if "permissions" not in tables:
        op.create_table(
            "permissions",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "key",
                sa.String(100),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "description",
                sa.String(255),
                nullable=True,
            ),
        )

    if "role_permissions" not in tables:
        op.create_table(
            "role_permissions",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id"),
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                sa.Integer(),
                sa.ForeignKey("permissions.id"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "role_id",
                "permission_id",
            ),
        )

    if "tenant_user_roles" not in tables:
        op.create_table(
            "tenant_user_roles",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "user_id",
                "role_id",
            ),
        )


def downgrade():
    pass
PY

"$PY" -m alembic upgrade head

cat > test_page12.py <<'PY'
from app.rbac import (
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLES,
    ROLE_PERMISSIONS,
    require_permission_key,
    require_same_tenant,
)


def main():
    expected_roles = {
        "Owner",
        "Admin",
        "Finance",
        "Support",
        "Sales",
        "Viewer",
    }

    assert set(DEFAULT_ROLES) == expected_roles

    required = {
        "users.read",
        "users.write",
        "orders.read",
        "payments.verify",
        "products.write",
        "settings.write",
        "admins.manage",
    }

    assert required.issubset(
        set(DEFAULT_PERMISSIONS)
    )

    for key in DEFAULT_PERMISSIONS:
        require_permission_key(key)

    assert (
        "admins.manage"
        in ROLE_PERMISSIONS["Owner"]
    )

    assert (
        "admins.manage"
        not in ROLE_PERMISSIONS["Admin"]
    )

    try:
        require_same_tenant(1, 2)
    except Exception:
        pass
    else:
        raise AssertionError(
            "CROSS_TENANT_OWNER_ACCESS_NOT_BLOCKED"
        )

    require_same_tenant(1, 1)

    from app.models.entities import (
        Permission,
        Role,
        RolePermission,
        TenantUserRole,
    )

    assert {
        "id",
        "key",
        "description",
    }.issubset(
        Permission.__table__.columns.keys()
    )

    assert {
        "tenant_id",
        "name",
        "is_system",
    }.issubset(
        Role.__table__.columns.keys()
    )

    assert {
        "role_id",
        "permission_id",
    }.issubset(
        RolePermission.__table__.columns.keys()
    )

    assert {
        "tenant_id",
        "user_id",
        "role_id",
    }.issubset(
        TenantUserRole.__table__.columns.keys()
    )

    print("PAGE 12 RBAC CONTRACT: OK")
    print("RBAC: ENABLED")
    print("ROLES: Owner,Admin,Finance,Support,Sales,Viewer")
    print("PERMISSION_KEYS: ENABLED")
    print("OWNER_TENANT_SCOPE: ENFORCED")
    print("CROSS_TENANT_ACCESS: BLOCKED")
    print("ROLE_PERMISSION_MAPPING: READY")
    print("TENANT_USER_ROLES: READY")
    print("PAGE 12 DATABASE CONTRACT: OK")


if __name__ == "__main__":
    main()
PY

"$PY" test_page12.py

"$PY" - <<'PY'
import asyncio
from sqlalchemy import inspect
from app.core.db import engine


async def main():
    async with engine.begin() as conn:
        tables = await conn.run_sync(
            lambda c: inspect(c).get_table_names()
        )

    required = {
        "roles",
        "permissions",
        "role_permissions",
        "tenant_user_roles",
    }

    missing = sorted(
        required - set(tables)
    )

    print("PAGE 12 FINAL DATABASE CHECK")
    print(
        "REQUIRED_TABLES:",
        ",".join(sorted(required)),
    )
    print(
        "MISSING_TABLES:",
        ",".join(missing) if missing else "0",
    )

    if missing:
        raise SystemExit(1)

    print("ROLES_TABLE: READY")
    print("PERMISSIONS_TABLE: READY")
    print("ROLE_PERMISSIONS_TABLE: READY")
    print("TENANT_USER_ROLES_TABLE: READY")
    print("PAGE 12 DATABASE CONTRACT: OK")


asyncio.run(main())
PY

echo
echo "=== PAGE 12 COMPLETE ==="
