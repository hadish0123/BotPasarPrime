from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Coupon, CouponUsage, Order, OrderItem, Plan, Product
from app.services.coupons import calculate_coupon_for_order
from app.shop_contract import PlanSnapshot, calculate_price


async def get_product(
    db: AsyncSession,
    tenant_id: int,
    product_id: int,
) -> Product | None:
    return await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
        )
    )


async def get_plan(
    db: AsyncSession,
    tenant_id: int,
    plan_id: int,
    active_only: bool = True,
) -> Plan | None:
    query = (
        select(Plan)
        .join(Product, Product.id == Plan.product_id)
        .where(
            Plan.id == plan_id,
            Product.tenant_id == tenant_id,
        )
    )
    if active_only:
        query = query.where(Plan.active.is_(True), Product.active.is_(True))
    return await db.scalar(query)


async def create_product(
    db: AsyncSession,
    tenant_id: int,
    name: str,
    description: str | None = None,
    category: str | None = None,
) -> Product:
    name = (name or "").strip()
    if not name or len(name) > 150:
        raise ValueError("invalid product name")
    if category is not None:
        category = category.strip()[:100] or None
    product = Product(
        tenant_id=tenant_id,
        name=name,
        description=description,
        category=category,
        active=True,
    )
    db.add(product)
    await db.flush()
    return product


async def create_plan(
    db: AsyncSession,
    tenant_id: int,
    product_id: int,
    name: str,
    price,
    duration_days: int,
    quota_gb: int | None = None,
    discount_kind: str = "none",
    discount_value=0,
) -> Plan:
    product = await get_product(db, tenant_id, product_id)
    if not product:
        raise ValueError("product_not_found")
    name = (name or "").strip()
    if not name or len(name) > 120:
        raise ValueError("invalid plan name")
    if duration_days <= 0:
        raise ValueError("duration must be greater than zero")
    if quota_gb is not None and quota_gb < 0:
        raise ValueError("quota cannot be negative")

    price_result = calculate_price(price, discount_kind, discount_value)
    plan = Plan(
        product_id=product.id,
        name=name,
        price=price_result.base_price,
        duration_days=duration_days,
        quota_gb=quota_gb,
        active=True,
        discount_kind=discount_kind,
        discount_value=Decimal(str(discount_value or 0)).quantize(Decimal("0.01")),
    )
    db.add(plan)
    await db.flush()
    return plan


async def build_plan_snapshot(
    db: AsyncSession,
    tenant_id: int,
    plan_id: int,
) -> tuple[Plan, Product, PlanSnapshot, Decimal]:
    plan = await get_plan(db, tenant_id, plan_id, active_only=True)
    if not plan:
        raise ValueError("plan_not_found")
    product = await get_product(db, tenant_id, plan.product_id)
    if not product or not product.active:
        raise ValueError("product_not_found")

    price = calculate_price(
        plan.price,
        plan.discount_kind or "none",
        plan.discount_value or 0,
    )
    snapshot = PlanSnapshot(
        product_name=product.name,
        plan_name=plan.name,
        price=price.final_price,
        duration_days=plan.duration_days,
        quota_gb=plan.quota_gb,
        category=product.category,
    )
    return plan, product, snapshot, price.final_price


async def create_order_from_plan(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
    plan_id: int,
    key: str,
    coupon_code: str | None = None,
) -> Order:
    if not tenant_id or not user_id:
        raise ValueError("tenant_id and user_id are required")
    key = (key or "").strip()
    if not key or len(key) > 100:
        raise ValueError("invalid idempotency key")

    old = await db.scalar(
        select(Order).where(
            Order.tenant_id == tenant_id,
            Order.idempotency_key == key,
        )
    )
    if old:
        if old.user_id != user_id:
            raise ValueError("idempotency key belongs to another user")
        return old

    plan, product, snapshot, final_price = await build_plan_snapshot(
        db,
        tenant_id,
        plan_id,
    )

    coupon = None
    discount = Decimal("0.00")
    if coupon_code:
        coupon = await db.scalar(
            select(Coupon)
            .where(
                Coupon.tenant_id == tenant_id,
                Coupon.code == coupon_code.strip().upper(),
                Coupon.active.is_(True),
            )
            .with_for_update()
        )
        if coupon is None:
            raise ValueError("coupon_not_found")
        _, discount = await calculate_coupon_for_order(
            db,
            tenant_id,
            coupon.code,
            final_price,
        )
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise ValueError("coupon_usage_limit_reached")

    total = max(Decimal("0.00"), final_price - discount).quantize(Decimal("0.01"))
    order = Order(
        tenant_id=tenant_id,
        user_id=user_id,
        status="created",
        total=total,
        idempotency_key=key,
    )
    db.add(order)
    await db.flush()

    item = OrderItem(
        order_id=order.id,
        plan_id=plan.id,
        quantity=1,
        unit_price=total,
        snapshot_product_name=snapshot.product_name,
        snapshot_plan_name=snapshot.plan_name,
        snapshot_price=total,
        snapshot_duration_days=snapshot.duration_days,
        snapshot_quota_gb=snapshot.quota_gb,
        snapshot_category=snapshot.category,
    )
    db.add(item)

    if coupon is not None:
        db.add(
            CouponUsage(
                coupon_id=coupon.id,
                user_id=user_id,
                order_id=order.id,
            )
        )
        coupon.used_count += 1

    await db.flush()
    return order
