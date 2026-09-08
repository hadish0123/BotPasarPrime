#!/usr/bin/env bash
set -euo pipefail

PY=".venv/bin/python"

echo "=== FIX PAGE 12 RBAC MODEL ==="

echo
echo "=== EXISTING RBAC MODELS ==="
grep -nE '^class (Role|Permission|RolePermission|TenantUserRole|UserRole|UserRoleAssignment)' \
    app/models/entities.py || true

echo
echo "=== EXISTING RBAC TABLES ==="

"$PY" - <<'PY'
import asyncio
from sqlalchemy import inspect
from app.core.db import engine


async def main():
    async with engine.begin() as conn:
        tables = await conn.run_sync(
            lambda c: inspect(c).get_table_names()
        )

    for name in (
        "roles",
        "permissions",
        "role_permissions",
        "tenant_user_roles",
    ):
        print(
            f"{name}:",
            "PRESENT" if name in tables else "MISSING",
        )


asyncio.run(main())
PY

cp app/models/entities.py app/models/entities.py.page12-fix-backup

"$PY" - <<'PY'
from pathlib import Path

p = Path("app/models/entities.py")
s = p.read_text()

# The Page 12 migration already created tenant_user_roles.
# The current ORM model is missing TenantUserRole, so add
# only that ORM mapping without touching the migration.

if "class TenantUserRole(Base):" in s:
    print("TENANT_USER_ROLE_MODEL: ALREADY_PRESENT")
else:
    marker = "\nclass Service(Base):"

    if marker not in s:
        raise SystemExit(
            "SERVICE_MODEL_MARKER_NOT_FOUND"
        )

    model = r'''
class TenantUserRole(Base):
    __tablename__ = 'tenant_user_roles'
    id: Mapped[int] = mapped_column(
        primary_key=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey('tenants.id'),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'),
        nullable=False,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey('roles.id'),
        nullable=False,
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
        "\n" + model + marker,
        1,
    )

    p.write_text(s)

    print("TENANT_USER_ROLE_MODEL: ADDED")

PY

echo
echo "=== VERIFY ORM IMPORTS ==="

"$PY" - <<'PY'
from app.models.entities import (
    Role,
    Permission,
    RolePermission,
    TenantUserRole,
)

print("Role: OK")
print("Permission: OK")
print("RolePermission: OK")
print("TenantUserRole: OK")

assert Role.__tablename__ == "roles"
assert Permission.__tablename__ == "permissions"
assert RolePermission.__tablename__ == "role_permissions"
assert TenantUserRole.__tablename__ == "tenant_user_roles"

print("RBAC ORM MODEL CONTRACT: OK")
PY

echo
echo "=== RUN PAGE 12 TEST ==="

"$PY" test_page12.py

echo
echo "=== FINAL DATABASE CHECK ==="

"$PY" - <<'PY'
import asyncio
from sqlalchemy import inspect
from app.core.db import engine


async def main():
    async with engine.begin() as conn:
        def inspect_db(c):
            inspector = inspect(c)

            tables = set(
                inspector.get_table_names()
            )

            result = {}

            for table in (
                "roles",
                "permissions",
                "role_permissions",
                "tenant_user_roles",
            ):
                if table in tables:
                    result[table] = [
                        column["name"]
                        for column in inspector.get_columns(
                            table
                        )
                    ]
                else:
                    result[table] = None

            return result

        result = await conn.run_sync(
            inspect_db
        )

    required = {
        "roles",
        "permissions",
        "role_permissions",
        "tenant_user_roles",
    }

    missing = [
        table
        for table in required
        if result.get(table) is None
    ]

    if missing:
        raise SystemExit(
            "MISSING_RBAC_TABLES: "
            + ",".join(missing)
        )

    required_columns = {
        "roles": {
            "id",
            "tenant_id",
            "name",
            "is_system",
        },
        "permissions": {
            "id",
            "key",
        },
        "role_permissions": {
            "role_id",
            "permission_id",
        },
        "tenant_user_roles": {
            "tenant_id",
            "user_id",
            "role_id",
        },
    }

    for table, expected in required_columns.items():
        actual = set(result[table])
        missing_columns = sorted(
            expected - actual
        )

        if missing_columns:
            raise SystemExit(
                f"{table} missing columns: "
                + ",".join(missing_columns)
            )

    print("PAGE 12 FINAL DATABASE CHECK")
    print("ROLES_TABLE: READY")
    print("PERMISSIONS_TABLE: READY")
    print("ROLE_PERMISSIONS_TABLE: READY")
    print("TENANT_USER_ROLES_TABLE: READY")
    print("RBAC_TENANT_ISOLATION: READY")
    print("PAGE 12 DATABASE CONTRACT: OK")


asyncio.run(main())
PY

echo
echo "=== PAGE 12 FIX COMPLETE ==="
