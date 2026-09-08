from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import PlanCreate, ProductCreate
from app.core.db import get_db
from app.models.entities import Plan, Product
from app.services.shop import (
    create_plan,
    create_product,
)

r = APIRouter(prefix="/shop", tags=["shop"])


@r.get("/products")
async def products(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.scalars(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.active.is_(True),
            )
        )
    ).all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "active": p.active,
        }
        for p in rows
    ]


@r.get("/products/{product_id}/plans")
async def product_plans(
    product_id: int,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.active.is_(True),
        )
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="product_not_found",
        )

    plans = (
        await db.scalars(
            select(Plan).where(
                Plan.product_id == product.id,
                Plan.active.is_(True),
            )
        )
    ).all()

    from app.shop_contract import calculate_price

    result = []

    for plan in plans:
        discount_kind = getattr(plan, "discount_kind", "none")
        discount_value = getattr(
            plan,
            "discount_value",
            0,
        )

        pricing = calculate_price(
            plan.price,
            discount_kind,
            discount_value,
        )

        result.append(
            {
                "id": plan.id,
                "name": plan.name,
                "base_price": str(pricing.base_price),
                "discount": str(pricing.discount),
                "price": str(pricing.final_price),
                "duration_days": plan.duration_days,
                "quota_gb": plan.quota_gb,
                "active": plan.active,
            }
        )

    return result


@r.post("/products")
async def create_product_route(
    x: ProductCreate,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        product = await create_product(
            db=db,
            tenant_id=tenant_id,
            name=x.name,
            description=x.description,
            category=x.category,
        )

        await db.commit()

        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "active": product.active,
        }

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None


@r.post("/plans")
async def create_plan_route(
    x: PlanCreate,
    product_id: int,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        plan = await create_plan(
            db=db,
            tenant_id=tenant_id,
            product_id=product_id,
            name=x.name,
            price=x.price,
            duration_days=x.duration_days,
            quota_gb=x.quota_gb,
            discount_kind=getattr(
                x,
                "discount_kind",
                "none",
            ),
            discount_value=getattr(
                x,
                "discount_value",
                0,
            ),
        )

        await db.commit()

        return {
            "id": plan.id,
            "name": plan.name,
            "price": str(plan.price),
            "duration_days": plan.duration_days,
            "quota_gb": plan.quota_gb,
            "active": plan.active,
        }

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None
