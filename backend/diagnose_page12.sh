#!/usr/bin/env bash
set -euo pipefail

PY=".venv/bin/python"

echo "=== PAGE 12 ORM DIAGNOSTIC ==="

"$PY" - <<'PY'
from app.models.entities import (
    Role,
    Permission,
    RolePermission,
    TenantUserRole,
)

models = (
    ("Role", Role),
    ("Permission", Permission),
    ("RolePermission", RolePermission),
    ("TenantUserRole", TenantUserRole),
)

for name, model in models:
    print()
    print(f"[{name}]")
    print("TABLE:", model.__tablename__)
    print(
        "COLUMNS:",
        ", ".join(
            model.__table__.columns.keys()
        )
    )

print()
print("=== REQUIRED PAGE 12 FIELDS ===")

checks = {
    "Role": (
        Role,
        {
            "id",
            "tenant_id",
            "name",
            "description",
            "is_system",
        },
    ),
    "Permission": (
        Permission,
        {
            "id",
            "key",
            "description",
        },
    ),
    "RolePermission": (
        RolePermission,
        {
            "id",
            "role_id",
            "permission_id",
        },
    ),
    "TenantUserRole": (
        TenantUserRole,
        {
            "id",
            "tenant_id",
            "user_id",
            "role_id",
        },
    ),
}

failed = False

for name, (model, required) in checks.items():
    actual = set(
        model.__table__.columns.keys()
    )
    missing = sorted(
        required - actual
    )

    if missing:
        failed = True
        print(
            f"{name}: MISSING -> "
            + ", ".join(missing)
        )
    else:
        print(f"{name}: OK")

print()

if failed:
    print("PAGE 12 ORM CONTRACT: NEEDS_ALIGNMENT")
else:
    print("PAGE 12 ORM CONTRACT: OK")

PY

echo
echo "=== RAW ENTITY DEFINITIONS ==="

sed -n '1,120p' app/models/entities.py

echo
echo "=== PAGE 12 DIAGNOSTIC COMPLETE ==="
