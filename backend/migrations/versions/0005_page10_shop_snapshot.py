
"""page10 shop, pricing and immutable order snapshots

Revision ID: 0005_page10_shop_snapshot
Revises: 0004_page9_payment_hardening
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_page10_shop_snapshot"
down_revision = "0004_page9_payment_hardening"
branch_labels = None
depends_on = None


def column_names(inspector, table):
    return {
        c["name"]
        for c in inspector.get_columns(table)
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    plan_columns = column_names(inspector, "plans")

    if "discount_kind" not in plan_columns:
        op.add_column(
            "plans",
            sa.Column(
                "discount_kind",
                sa.String(20),
                nullable=False,
                server_default="none",
            ),
        )

    if "discount_value" not in plan_columns:
        op.add_column(
            "plans",
            sa.Column(
                "discount_value",
                sa.Numeric(18, 2),
                nullable=False,
                server_default="0",
            ),
        )

    item_columns = column_names(inspector, "order_items")

    additions = [
        (
            "snapshot_product_name",
            sa.String(150),
        ),
        (
            "snapshot_plan_name",
            sa.String(120),
        ),
        (
            "snapshot_price",
            sa.Numeric(18, 2),
        ),
        (
            "snapshot_duration_days",
            sa.Integer(),
        ),
        (
            "snapshot_quota_gb",
            sa.Integer(),
        ),
        (
            "snapshot_category",
            sa.String(100),
        ),
    ]

    for name, column in additions:
        if name not in item_columns:
            op.add_column(
                "order_items",
                sa.Column(
                    name,
                    column,
                    nullable=True,
                ),
            )

    # Product catalog lookup.
    product_indexes = {
        i["name"]
        for i in inspector.get_indexes("products")
    }

    if "ix_products_tenant_category" not in product_indexes:
        op.create_index(
            "ix_products_tenant_category",
            "products",
            ["tenant_id", "category"],
            unique=False,
        )

    # Plan catalog lookup.
    plan_indexes = {
        i["name"]
        for i in inspector.get_indexes("plans")
    }

    if "ix_plans_product_active" not in plan_indexes:
        op.create_index(
            "ix_plans_product_active",
            "plans",
            ["product_id", "active"],
            unique=False,
        )

    # Snapshot lookup.
    item_indexes = {
        i["name"]
        for i in inspector.get_indexes("order_items")
    }

    if "ix_order_items_order" not in item_indexes:
        op.create_index(
            "ix_order_items_order",
            "order_items",
            ["order_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for index_name, table_name in [
        ("ix_products_tenant_category", "products"),
        ("ix_plans_product_active", "plans"),
        ("ix_order_items_order", "order_items"),
    ]:
        indexes = {
            i["name"]
            for i in inspector.get_indexes(table_name)
        }

        if index_name in indexes:
            op.drop_index(
                index_name,
                table_name=table_name,
            )

    item_columns = column_names(inspector, "order_items")

    for name in [
        "snapshot_product_name",
        "snapshot_plan_name",
        "snapshot_price",
        "snapshot_duration_days",
        "snapshot_quota_gb",
        "snapshot_category",
    ]:
        if name in item_columns:
            op.drop_column(
                "order_items",
                name,
            )

    plan_columns = column_names(inspector, "plans")

    if "discount_value" in plan_columns:
        op.drop_column(
            "plans",
            "discount_value",
        )

    if "discount_kind" in plan_columns:
        op.drop_column(
            "plans",
            "discount_kind",
        )
