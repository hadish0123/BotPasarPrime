"""Page 8 data model completion.

This migration is intentionally additive. Existing tables from the initial
migration are preserved. Missing relational structures required by the
3XSHOP data-model contract are added here.
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_page8_data_model"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _index_exists(bind, table: str, name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        index.get("name") == name
        for index in inspector.get_indexes(table)
    )


def upgrade() -> None:
    bind = op.get_bind()

    # Users can have tenant-scoped roles.
    # This is distinct from AdminRole, which belongs to platform/tenant admins.
    if not _table_exists(bind, "user_roles"):
        op.create_table(
            "user_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "user_id",
                "role_id",
                "tenant_id",
                name="uq_user_roles_user_role_tenant",
            ),
        )

    if _table_exists(bind, "user_roles"):
        if not _index_exists(
            bind,
            "user_roles",
            "ix_user_roles_tenant_id",
        ):
            op.create_index(
                "ix_user_roles_tenant_id",
                "user_roles",
                ["tenant_id"],
            )

        if not _index_exists(
            bind,
            "user_roles",
            "ix_user_roles_user_id",
        ):
            op.create_index(
                "ix_user_roles_user_id",
                "user_roles",
                ["user_id"],
            )

        if not _index_exists(
            bind,
            "user_roles",
            "ix_user_roles_role_id",
        ):
            op.create_index(
                "ix_user_roles_role_id",
                "user_roles",
                ["role_id"],
            )

    # Explicit tenant lookup indexes for the business model.
    tenant_tables = (
        "tenant_credentials",
        "tenant_branding",
        "bots",
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
    )

    for table in tenant_tables:
        if not _table_exists(bind, table):
            continue

        columns = {
            column["name"]
            for column in sa.inspect(bind).get_columns(table)
        }

        if "tenant_id" not in columns:
            continue

        index_name = f"ix_{table}_tenant_id"

        if not _index_exists(bind, table, index_name):
            op.create_index(
                index_name,
                table,
                ["tenant_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "user_roles"):
        for index_name in (
            "ix_user_roles_role_id",
            "ix_user_roles_user_id",
            "ix_user_roles_tenant_id",
        ):
            if _index_exists(bind, "user_roles", index_name):
                op.drop_index(index_name, table_name="user_roles")

        op.drop_table("user_roles")

    tenant_tables = (
        "tenant_credentials",
        "tenant_branding",
        "bots",
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
    )

    for table in tenant_tables:
        if not _table_exists(bind, table):
            continue

        index_name = f"ix_{table}_tenant_id"

        if _index_exists(bind, table, index_name):
            op.drop_index(index_name, table_name=table)
