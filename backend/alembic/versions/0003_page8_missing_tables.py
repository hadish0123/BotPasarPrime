"""Complete missing tables required by Page 8 data model."""

from alembic import op
import sqlalchemy as sa


revision = "0003_page8_missing_tables"
down_revision = "0002_page8_data_model"
branch_labels = None
depends_on = None


def table_exists(bind, name):
    return name in sa.inspect(bind).get_table_names()


def index_exists(bind, table, name):
    return any(
        i.get("name") == name
        for i in sa.inspect(bind).get_indexes(table)
    )


def upgrade():
    bind = op.get_bind()

    if not table_exists(bind, "bots"):
        op.create_table(
            "bots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("encrypted_token", sa.Text(), nullable=False),
            sa.Column("masked_token", sa.String(255), nullable=False),
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
            sa.Column(
                "error_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "name",
                name="uq_bots_tenant_name",
            ),
        )

    if table_exists(bind, "bots") and not index_exists(
        bind, "bots", "ix_bots_tenant_id"
    ):
        op.create_index(
            "ix_bots_tenant_id",
            "bots",
            ["tenant_id"],
        )

    if not table_exists(bind, "user_roles"):
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

    if table_exists(bind, "user_roles"):
        for name, column in (
            ("ix_user_roles_user_id", "user_id"),
            ("ix_user_roles_role_id", "role_id"),
            ("ix_user_roles_tenant_id", "tenant_id"),
        ):
            if not index_exists(bind, "user_roles", name):
                op.create_index(
                    name,
                    "user_roles",
                    [column],
                )

    if not table_exists(bind, "settings"):
        op.create_table(
            "settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(255), nullable=False),
            sa.Column("value", sa.Text(), nullable=True),
            sa.UniqueConstraint(
                "key",
                name="uq_settings_key",
            ),
        )


def downgrade():
    bind = op.get_bind()

    if table_exists(bind, "settings"):
        op.drop_table("settings")

    if table_exists(bind, "user_roles"):
        for name in (
            "ix_user_roles_tenant_id",
            "ix_user_roles_role_id",
            "ix_user_roles_user_id",
        ):
            if index_exists(bind, "user_roles", name):
                op.drop_index(name, table_name="user_roles")
        op.drop_table("user_roles")

    if table_exists(bind, "bots"):
        if index_exists(bind, "bots", "ix_bots_tenant_id"):
            op.drop_index("ix_bots_tenant_id", table_name="bots")
        op.drop_table("bots")
