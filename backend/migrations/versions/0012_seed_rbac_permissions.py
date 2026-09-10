"""Seed canonical RBAC permissions and system roles."""

import sqlalchemy as sa
from alembic import op

revision = "0012_seed_rbac_permissions"
down_revision = "0011_onboarding_payments"
branch_labels = None
depends_on = None

ROLE_PERMISSIONS = {
    "Owner": "*",
    "Admin": "*,-admins.write",
    "Finance": "dashboard.read,orders.read,payments.read,payments.verify,payments.refund,wallet.read,wallet.write,reports.read",
    "Support": "dashboard.read,users.read,tickets.read,tickets.reply,orders.read,services.read",
    "Sales": "dashboard.read,users.read,products.read,products.write,orders.read,orders.write,coupons.read,coupons.write,referrals.read,referrals.write",
    "Viewer": "dashboard.read,tenants.read,users.read,products.read,orders.read,payments.read,wallet.read,reports.read,settings.read,audit.read,services.read",
}
PERMISSIONS = [
    "dashboard.read", "tenants.read", "tenants.write", "tenants.approve", "users.read", "users.write",
    "products.read", "products.write", "orders.read", "orders.write", "payments.read", "payments.verify",
    "payments.refund", "wallet.read", "wallet.write", "coupons.read", "coupons.write", "referrals.read",
    "referrals.write", "tickets.read", "tickets.reply", "bots.read", "bots.write", "audit.read", "reports.read",
    "services.read", "services.write", "settings.read", "settings.write", "admins.read", "admins.write", "auth.telegram",
]

def _columns(bind, table_name):
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}

def upgrade():
    bind = op.get_bind()
    permission_columns = _columns(bind, "permissions")
    role_columns = _columns(bind, "roles")
    role_permission_columns = _columns(bind, "role_permissions")
    permission = sa.table("permissions", *(sa.column(name) for name in permission_columns))
    role = sa.table("roles", *(sa.column(name) for name in role_columns))
    role_permission = sa.table("role_permissions", *(sa.column(name) for name in role_permission_columns))
    existing_permissions = {row.key: row.id for row in bind.execute(sa.select(permission.c.key, permission.c.id)).all()}
    for key in PERMISSIONS:
        if key not in existing_permissions:
            values = {"key": key}
            if "description" in permission_columns:
                values["description"] = key.replace(".", " ")
            bind.execute(permission.insert().values(**values))
    existing_permissions = {row.key: row.id for row in bind.execute(sa.select(permission.c.key, permission.c.id)).all()}
    role_select = [role.c.name, role.c.id]
    if "tenant_id" in role_columns:
        role_select.append(role.c.tenant_id)
        existing_roles = {row.name: row.id for row in bind.execute(sa.select(*role_select).where(role.c.tenant_id.is_(None))).all()}
    else:
        existing_roles = {row.name: row.id for row in bind.execute(sa.select(role.c.name, role.c.id)).all()}
    for name in ROLE_PERMISSIONS:
        if name not in existing_roles:
            values = {"name": name}
            if "description" in role_columns: values["description"] = f"System role: {name}"
            if "tenant_id" in role_columns: values["tenant_id"] = None
            if "is_system" in role_columns: values["is_system"] = True
            if "created_at" in role_columns: values["created_at"] = sa.func.now()
            bind.execute(role.insert().values(**values))
    if "tenant_id" in role_columns:
        existing_roles = {row.name: row.id for row in bind.execute(sa.select(role.c.name, role.c.id).where(role.c.tenant_id.is_(None))).all()}
    for role_name, expression in ROLE_PERMISSIONS.items():
        keys = set(PERMISSIONS) if expression == "*" else {item for item in expression.split(",") if item}
        if expression == "*,-admins.write": keys = set(PERMISSIONS) - {"admins.write"}
        for key in keys:
            if not bind.execute(sa.select(role_permission.c.role_id).where(role_permission.c.role_id == existing_roles[role_name], role_permission.c.permission_id == existing_permissions[key])).first():
                bind.execute(role_permission.insert().values(role_id=existing_roles[role_name], permission_id=existing_permissions[key]))

def downgrade():
    pass
