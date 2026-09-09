"""Page 8 relational indexes and schema hardening.

The complete table set is created by the initial migration from the canonical
SQLAlchemy metadata. This revision only adds missing tenant lookup indexes.
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_page8_data_model"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _index_exists(bind, table: str, name: str) -> bool:
    return any(
        index.get("name") == name
        for index in sa.inspect(bind).get_indexes(table)
    )


def upgrade() -> None:
    bind = op.get_bind()
    tenant_tables = (
        "tenant_credentials",
        "tenant_branding",
        "bot_instances",
        "tenant_users",
        "products",
        "orders",
        "payments",
        "wallets",
        "coupons",
        "referrals",
        "services",
        "tickets",
        "notifications",
        "broadcasts",
        "audit_logs",
        "approval_requests",
    )

    for table in tenant_tables:
        if not _table_exists(bind, table):
            continue
        columns = {
            column["name"] for column in sa.inspect(bind).get_columns(table)
        }
        if "tenant_id" not in columns:
            continue
        index_name = f"ix_{table}_tenant_id"
        if not _index_exists(bind, table, index_name):
            op.create_index(index_name, table, ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tenant_tables = (
        "tenant_credentials",
        "tenant_branding",
        "bot_instances",
        "tenant_users",
        "products",
        "orders",
        "payments",
        "wallets",
        "coupons",
        "referrals",
        "services",
        "tickets",
        "notifications",
        "broadcasts",
        "audit_logs",
        "approval_requests",
    )

    for table in tenant_tables:
        if not _table_exists(bind, table):
            continue
        index_name = f"ix_{table}_tenant_id"
        if _index_exists(bind, table, index_name):
            op.drop_index(index_name, table_name=table)
