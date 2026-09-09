"""Create onboarding activation payment records."""

import sqlalchemy as sa
from alembic import op

revision = "0011_onboarding_payments"
down_revision = "0010_production_hardening"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _table_exists(op.get_bind(), "onboarding_payments"):
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_onboarding_payment_tenant_key"),
    )


def downgrade() -> None:
    if _table_exists(op.get_bind(), "onboarding_payments"):
        op.drop_table("onboarding_payments")
