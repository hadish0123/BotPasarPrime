"""Seed canonical RBAC permission catalog.

Revision ID: 0012_seed_rbac_permissions
Revises: 0011_onboarding_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_seed_rbac_permissions"
down_revision = "0011_onboarding_payments"
branch_labels = None
depends_on = None

PERMISSIONS = [
    "dashboard.read", "tenants.read", "tenants.write", "tenants.approve",
    "users.read", "users.write", "products.read", "products.write",
    "orders.read", "orders.write", "payments.read", "payments.verify",
    "payments.refund", "wallet.read", "wallet.write", "coupons.read",
    "coupons.write", "referrals.read", "referrals.write", "tickets.read",
    "tickets.reply", "bots.read", "bots.write", "audit.read", "reports.read",
    "services.read", "services.write", "settings.read", "settings.write",
    "admins.read", "admins.write", "auth.telegram",
]


def upgrade() -> None:
    bind = op.get_bind()
    table = sa.table("permissions", sa.column("key", sa.String(100)), sa.column("description", sa.String(255)))
    existing = {row[0] for row in bind.execute(sa.select(table.c.key)).all()}
    rows = [{"key": key, "description": key.replace(".", " ")} for key in PERMISSIONS if key not in existing]
    if rows:
        bind.execute(table.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)"), {"keys": PERMISSIONS})
