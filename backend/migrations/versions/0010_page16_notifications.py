"""page16 notifications and scheduler idempotency

Revision ID: 0010_page16_notifications
Revises: 0009
Create Date: 2026-09-08
"""

import sqlalchemy as sa

from alembic import op

revision = "0010_page16_notifications"
down_revision = "0008_page12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("notification_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_notification_deliveries_event_key",
        "notification_deliveries",
        ["event_key"],
        unique=True,
    )

    op.create_index(
        "ix_notification_deliveries_recipient",
        "notification_deliveries",
        ["recipient_id"],
    )

    op.create_table(
        "scheduler_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("run_key", sa.String(255), nullable=False),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_scheduler_runs_run_key",
        "scheduler_runs",
        ["run_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduler_runs_run_key",
        table_name="scheduler_runs",
    )
    op.drop_table("scheduler_runs")

    op.drop_index(
        "ix_notification_deliveries_recipient",
        table_name="notification_deliveries",
    )
    op.drop_index(
        "ix_notification_deliveries_event_key",
        table_name="notification_deliveries",
    )
    op.drop_table("notification_deliveries")
