#!/usr/bin/env bash
set -euo pipefail

echo "=== FIX PAGE 12 ORM ALIGNMENT ==="

cp app/models/entities.py "app/models/entities.py.page12-rbac-backup-$(date +%Y%m%d-%H%M%S)"

.venv/bin/python - <<'PY'
from pathlib import Path

p = Path("app/models/entities.py")
s = p.read_text()

old_role = """class Role(Base):
    __tablename__='roles'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(50),unique=True); scope:Mapped[str]=mapped_column(String(20),default='tenant')
"""

new_role = """class Role(Base):
    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
        nullable=False,
    )
"""

old_permission = """class Permission(Base):
    __tablename__='permissions'; id:Mapped[int]=mapped_column(primary_key=True); key:Mapped[str]=mapped_column(String(100),unique=True)
"""

new_permission = """class Permission(Base):
    __tablename__ = 'permissions'

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
"""

if old_role not in s:
    raise SystemExit("OLD_ROLE_DEFINITION_NOT_FOUND")

if old_permission not in s:
    raise SystemExit("OLD_PERMISSION_DEFINITION_NOT_FOUND")

s = s.replace(old_role, new_role)
s = s.replace(old_permission, new_permission)

p.write_text(s)

print("ROLE_ORM_ALIGNED")
print("PERMISSION_ORM_ALIGNED")
PY

echo
echo "=== VERIFY ORM ==="

.venv/bin/python - <<'PY'
from app.models.entities import Role, Permission, RolePermission, TenantUserRole

print("Role:", ", ".join(Role.__table__.columns.keys()))
print("Permission:", ", ".join(Permission.__table__.columns.keys()))
print("RolePermission:", ", ".join(RolePermission.__table__.columns.keys()))
print("TenantUserRole:", ", ".join(TenantUserRole.__table__.columns.keys()))

required_role = {
    "id",
    "tenant_id",
    "name",
    "description",
    "is_system",
    "created_at",
}

required_permission = {
    "id",
    "key",
    "description",
}

assert required_role.issubset(Role.__table__.columns.keys())
assert required_permission.issubset(Permission.__table__.columns.keys())

print("ROLE_ORM_CONTRACT: OK")
print("PERMISSION_ORM_CONTRACT: OK")
print("PAGE 12 ORM ALIGNMENT: OK")
PY

echo
echo "=== RUN PAGE 12 TEST ==="

.venv/bin/python test_page12.py

echo
echo "=== PAGE 12 ORM ALIGNMENT COMPLETE ==="
