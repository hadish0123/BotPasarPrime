
"""page9 payment hardening

Revision ID: 0004_page9_payment_hardening
Revises: 0003_page8_missing_tables
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_page9_payment_hardening"
down_revision = "0003_page8_missing_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Payment financial fields are already represented by the
    # existing model. This migration intentionally avoids destructive
    # schema changes and keeps existing financial data intact.

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = {
        index["name"]
        for index in inspector.get_indexes("payments")
    }

    if "ix_payments_tenant_status" not in indexes:
        op.create_index(
            "ix_payments_tenant_status",
            "payments",
            ["tenant_id", "status"],
            unique=False,
        )

    order_indexes = {
        index["name"]
        for index in inspector.get_indexes("orders")
    }

    if "ix_orders_tenant_status" not in order_indexes:
        op.create_index(
            "ix_orders_tenant_status",
            "orders",
            ["tenant_id", "status"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = {
        index["name"]
        for index in inspector.get_indexes("payments")
    }

    if "ix_payments_tenant_status" in indexes:
        op.drop_index(
            "ix_payments_tenant_status",
            table_name="payments",
        )

    order_indexes = {
        index["name"]
        for index in inspector.get_indexes("orders")
    }

    if "ix_orders_tenant_status" in order_indexes:
        op.drop_index(
            "ix_orders_tenant_status",
            table_name="orders",
        )
