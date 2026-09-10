"""Make custom role names tenant-scoped while keeping global roles unique.

Revision ID: 0014_tenant_scoped_role_names
Revises: 0013_schema_alignment
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_tenant_scoped_role_names"
down_revision = "0013_schema_alignment"
branch_labels = None
depends_on = None


def _unique_constraints(bind, table: str):
    return sa.inspect(bind).get_unique_constraints(table)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "roles" not in tables:
        return

    for constraint in _unique_constraints(bind, "roles"):
        columns = tuple(constraint.get("column_names") or ())
        if columns in (("name",), ("tenant_id", "name")):
            name = constraint.get("name")
            if name:
                op.drop_constraint(name, "roles", type_="unique")

    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("roles") if i.get("name")}
    if "uq_roles_global_name" not in indexes:
        op.create_index(
            "uq_roles_global_name", "roles", ["name"], unique=True,
            postgresql_where=sa.text("tenant_id IS NULL"),
        )
    if "uq_roles_tenant_name" not in indexes:
        op.create_index(
            "uq_roles_tenant_name", "roles", ["tenant_id", "name"], unique=True,
            postgresql_where=sa.text("tenant_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "roles" not in tables:
        return
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("roles") if i.get("name")}
    if "uq_roles_tenant_name" in indexes:
        op.drop_index("uq_roles_tenant_name", table_name="roles")
    if "uq_roles_global_name" in indexes:
        op.drop_index("uq_roles_global_name", table_name="roles")
    op.create_unique_constraint("uq_roles_name_legacy", "roles", ["name"])
