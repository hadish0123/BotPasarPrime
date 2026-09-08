"""Page 12 RBAC

Revision ID: 0008_page12
Revises: 0007_page11
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_page12"
down_revision = "0007_page11"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "roles" not in tables:
        op.create_table(
            "roles",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id"),
                nullable=True,
            ),
            sa.Column(
                "name",
                sa.String(50),
                nullable=False,
            ),
            sa.Column(
                "description",
                sa.String(255),
                nullable=True,
            ),
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "name",
            ),
        )

    if "permissions" not in tables:
        op.create_table(
            "permissions",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "key",
                sa.String(100),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "description",
                sa.String(255),
                nullable=True,
            ),
        )

    if "role_permissions" not in tables:
        op.create_table(
            "role_permissions",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id"),
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                sa.Integer(),
                sa.ForeignKey("permissions.id"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "role_id",
                "permission_id",
            ),
        )

    if "tenant_user_roles" not in tables:
        op.create_table(
            "tenant_user_roles",
            sa.Column(
                "id",
                sa.Integer(),
                primary_key=True,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("roles.id"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "user_id",
                "role_id",
            ),
        )


def downgrade():
    pass
