"""Add notification read timestamps."""

import sqlalchemy as sa
from alembic import op

revision = "0012_notification_read_state"
down_revision = "0011_onboarding_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("notifications")}
    if "read_at" not in columns:
        op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("notifications")}
    if "read_at" in columns:
        op.drop_column("notifications", "read_at")
