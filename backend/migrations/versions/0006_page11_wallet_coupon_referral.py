"""Page 11 wallet coupon referral hardening

Revision ID: 0006_page11
Revises: 0005_page10
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_page11"
down_revision = "0005_page10_shop_snapshot"
branch_labels = None
depends_on = None


def _columns(table):
    inspector = sa.inspect(op.get_bind())
    return {
        c["name"]
        for c in inspector.get_columns(table)
    }


def upgrade():
    bind = op.get_bind()

    if "coupons" in sa.inspect(bind).get_table_names():
        cols = _columns("coupons")

        if "coupon_type" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "coupon_type",
                    sa.String(20),
                    nullable=False,
                    server_default="fixed",
                ),
            )

        if "value" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "value",
                    sa.Numeric(18, 2),
                    nullable=False,
                    server_default="0",
                ),
            )

        if "minimum_purchase" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "minimum_purchase",
                    sa.Numeric(18, 2),
                    nullable=False,
                    server_default="0",
                ),
            )

        if "maximum_discount" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "maximum_discount",
                    sa.Numeric(18, 2),
                    nullable=True,
                ),
            )

        if "starts_at" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "starts_at",
                    sa.DateTime(),
                    nullable=True,
                ),
            )

        if "expires_at" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "expires_at",
                    sa.DateTime(),
                    nullable=True,
                ),
            )

        if "usage_limit" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "usage_limit",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "used_count" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "used_count",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )

        indexes = {
            x["name"]
            for x in sa.inspect(bind).get_indexes("coupons")
        }
        if "ix_coupons_tenant_code" not in indexes:
            op.create_index(
                "ix_coupons_tenant_code",
                "coupons",
                ["tenant_id", "code"],
                unique=True,
            )

    tables = sa.inspect(bind).get_table_names()

    if "referrals" in tables:
        cols = _columns("referrals")

        if "referrer_user_id" not in cols:
            op.add_column(
                "referrals",
                sa.Column(
                    "referrer_user_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "referred_user_id" not in cols:
            op.add_column(
                "referrals",
                sa.Column(
                    "referred_user_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        indexes = {
            x["name"]
            for x in sa.inspect(bind).get_indexes("referrals")
        }
        if "ix_referrals_tenant_referred" not in indexes:
            op.create_index(
                "ix_referrals_tenant_referred",
                "referrals",
                ["tenant_id", "referred_user_id"],
                unique=True,
            )


def downgrade():
    pass
