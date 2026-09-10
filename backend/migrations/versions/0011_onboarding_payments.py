"""Tenant onboarding payment records.

Revision ID: 0011_onboarding_payments
Revises: 0010_page16_notifications
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_onboarding_payments"
down_revision = "0010_page16_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "onboarding_payments" in inspector.get_table_names():
        return
    op.create_table(
        "onboarding_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(30), nullable=False, server_default="awaiting_payment"),
        sa.Column("reference", sa.String(150), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_onboarding_payment_tenant_key"),
    )
    op.create_index("ix_onboarding_payments_tenant_status", "onboarding_payments", ["tenant_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "onboarding_payments" not in inspector.get_table_names():
        return
    indexes = {item["name"] for item in inspector.get_indexes("onboarding_payments")}
    if "ix_onboarding_payments_tenant_status" in indexes:
        op.drop_index("ix_onboarding_payments_tenant_status", table_name="onboarding_payments")
    op.drop_table("onboarding_payments")
