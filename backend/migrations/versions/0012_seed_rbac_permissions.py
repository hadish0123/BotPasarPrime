"""Seed canonical RBAC permissions and system roles.

Revision ID: 0012_seed_rbac_permissions
Revises: 0011_onboarding_payments
"""

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


def upgrade() -> None:
    bind = op.get_bind()
    permission = sa.table("permissions", sa.column("id", sa.Integer), sa.column("key", sa.String(100)), sa.column("description", sa.String(255)))
    role = sa.table("roles", sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer), sa.column("name", sa.String(50)), sa.column("description", sa.String(255)), sa.column("is_system", sa.Boolean))
    role_permission = sa.table("role_permissions", sa.column("role_id", sa.Integer), sa.column("permission_id", sa.Integer))

    existing_permissions = {row.key: row.id for row in bind.execute(sa.select(permission.c.key, permission.c.id)).all()}
    for key in PERMISSIONS:
        if key not in existing_permissions:
            bind.execute(permission.insert().values(key=key, description=key.replace(".", " ")))
    existing_permissions = {row.key: row.id for row in bind.execute(sa.select(permission.c.key, permission.c.id)).all()}

    existing_roles = {row.name: row.id for row in bind.execute(sa.select(role.c.name, role.c.id).where(role.c.tenant_id.is_(None))).all()}
    for name in ROLE_PERMISSIONS:
        if name not in existing_roles:
            bind.execute(role.insert().values(tenant_id=None, name=name, description=f"System role: {name}", is_system=True))
    existing_roles = {row.name: row.id for row in bind.execute(sa.select(role.c.name, role.c.id).where(role.c.tenant_id.is_(None))).all()}

    all_permissions = set(PERMISSIONS)
    for role_name, expression in ROLE_PERMISSIONS.items():
        keys = all_permissions if expression == "*" else {item for item in expression.split(",") if item}
        if expression == "*,-admins.write":
            keys = all_permissions - {"admins.write"}
        for key in keys:
            bind.execute(role_permission.insert().from_select(["role_id", "permission_id"], sa.select(sa.literal(existing_roles[role_name]), sa.literal(existing_permissions[key])).where(~sa.exists(sa.select(role_permission.c.role_id).where(role_permission.c.role_id == existing_roles[role_name], role_permission.c.permission_id == existing_permissions[key])))))


def downgrade() -> None:
    bind = op.get_bind()
    permission = sa.table("permissions", sa.column("id", sa.Integer), sa.column("key", sa.String(100)))
    role = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String(50)), sa.column("tenant_id", sa.Integer))
    role_permission = sa.table("role_permissions", sa.column("role_id", sa.Integer))
    role_ids = [row.id for row in bind.execute(sa.select(role.c.id).where(role.c.tenant_id.is_(None), role.c.name.in_(list(ROLE_PERMISSIONS)))).all()]
    if role_ids:
        bind.execute(role_permission.delete().where(role_permission.c.role_id.in_(role_ids)))
        bind.execute(role.delete().where(role.c.id.in_(role_ids)))
    bind.execute(permission.delete().where(permission.c.key.in_(PERMISSIONS)))
