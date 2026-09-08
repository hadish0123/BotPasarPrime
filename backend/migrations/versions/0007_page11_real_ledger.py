"""Page 11 real coupon/referral ledger

Revision ID: 0007_page11
Revises: 0006_page11
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_page11"
down_revision = "0006_page11"
branch_labels = None
depends_on = None


def columns(bind, table):
    return {
        c["name"]
        for c in sa.inspect(bind).get_columns(table)
    }


def indexes(bind, table):
    return {
        x["name"]
        for x in sa.inspect(bind).get_indexes(table)
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # -----------------------------------------------------
    # Coupons
    # -----------------------------------------------------
    if "coupons" in tables:
        cols = columns(bind, "coupons")

        if "starts_at" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "starts_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                ),
            )

        if "expires_at" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "expires_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                ),
            )

        idx = indexes(bind, "coupons")

        if "ix_coupons_tenant_code" not in idx:
            op.create_index(
                "ix_coupons_tenant_code",
                "coupons",
                ["tenant_id", "code"],
                unique=True,
            )

    # -----------------------------------------------------
    # Referrals
    # -----------------------------------------------------
    if "referrals" in tables:
        cols = columns(bind, "referrals")

        idx = indexes(bind, "referrals")

        if "ix_referrals_tenant_code" not in idx:
            op.create_index(
                "ix_referrals_tenant_code",
                "referrals",
                ["tenant_id", "code"],
                unique=True,
            )

    # -----------------------------------------------------
    # Referral commission ledger
    # -----------------------------------------------------
    if "referral_transactions" in tables:
        cols = columns(bind, "referral_transactions")

        if "tenant_id" not in cols:
            op.add_column(
                "referral_transactions",
                sa.Column(
                    "tenant_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "order_id" not in cols:
            op.add_column(
                "referral_transactions",
                sa.Column(
                    "order_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "user_id" not in cols:
            op.add_column(
                "referral_transactions",
                sa.Column(
                    "user_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "commission_percent" not in cols:
            op.add_column(
                "referral_transactions",
                sa.Column(
                    "commission_percent",
                    sa.Numeric(8, 4),
                    nullable=False,
                    server_default="0",
                ),
            )

        if "ledger_type" not in cols:
            op.add_column(
                "referral_transactions",
                sa.Column(
                    "ledger_type",
                    sa.String(30),
                    nullable=False,
                    server_default="commission",
                ),
            )

        if "created_at" not in cols:
            op.add_column(
                "referral_transactions",
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                ),
            )

        idx = indexes(bind, "referral_transactions")

        if "ix_referral_transactions_tenant" not in idx:
            op.create_index(
                "ix_referral_transactions_tenant",
                "referral_transactions",
                ["tenant_id"],
                unique=False,
            )

        if "ix_referral_transactions_order" not in idx:
            op.create_index(
                "ix_referral_transactions_order",
                "referral_transactions",
                ["order_id"],
                unique=False,
            )


def downgrade():
    pass
