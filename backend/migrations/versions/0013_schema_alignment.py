"""Align legacy databases with the production ORM schema.

Revision ID: 0013_schema_alignment
Revises: 0012_seed_rbac_permissions
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_schema_alignment"
down_revision = "0012_seed_rbac_permissions"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _add_column_if_missing(bind, table: str, column: sa.Column) -> None:
    if column.name not in _columns(bind, table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "roles" in tables:
        _add_column_if_missing(
            bind,
            "roles",
            sa.Column("tenant_id", sa.Integer(), nullable=True),
        )
        _add_column_if_missing(
            bind,
            "roles",
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        _add_column_if_missing(
            bind,
            "roles",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        bind.execute(
            sa.text(
                "UPDATE roles SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                "WHERE created_at IS NULL"
            )
        )
        bind.execute(sa.text("UPDATE roles SET is_system = FALSE WHERE is_system IS NULL"))
        if "ix_roles_tenant_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("roles") if i.get("name")}: 
            op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

    if "permissions" in tables:
        _add_column_if_missing(
            bind,
            "permissions",
            sa.Column("description", sa.String(255), nullable=True),
        )

    if "notifications" in tables:
        _add_column_if_missing(
            bind,
            "notifications",
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )
        _add_column_if_missing(
            bind,
            "notifications",
            sa.Column("idempotency_key", sa.String(150), nullable=True),
        )
        bind.execute(
            sa.text(
                "UPDATE notifications SET idempotency_key = 'legacy-notification-' || id::text "
                "WHERE idempotency_key IS NULL"
            )
        )
        op.alter_column("notifications", "idempotency_key", nullable=False)
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes("notifications") if i.get("name")}
        if "ix_notifications_idempotency_key" not in indexes:
            op.create_index(
                "ix_notifications_idempotency_key",
                "notifications",
                ["idempotency_key"],
                unique=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "notifications" in tables:
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes("notifications") if i.get("name")}
        if "ix_notifications_idempotency_key" in indexes:
            op.drop_index("ix_notifications_idempotency_key", table_name="notifications")
        columns = _columns(bind, "notifications")
        if "idempotency_key" in columns:
            op.drop_column("notifications", "idempotency_key")
        if "read_at" in columns:
            op.drop_column("notifications", "read_at")
    if "permissions" in tables and "description" in _columns(bind, "permissions"):
        op.drop_column("permissions", "description")
    if "roles" in tables:
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes("roles") if i.get("name")}
        if "ix_roles_tenant_id" in indexes:
            op.drop_index("ix_roles_tenant_id", table_name="roles")
        columns = _columns(bind, "roles")
        for name in ("created_at", "is_system", "tenant_id"):
            if name in columns:
                op.drop_column("roles", name)
