from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.api.schemas import PlanCreate, ProductCreate
from app.core.db import get_db
from app.models.entities import Plan, Product
from app.services.shop import create_plan, create_product
from app.shop_contract import calculate_price

r = APIRouter(prefix="/shop", tags=["shop"])


def _tenant(claims, tenant_id: int) -> None:
    require_tenant_match(tenant_id, claims)


@r.get("/products")
async def products(
    tenant_id: int,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    permissions = claims.get("permissions", [])
    if "products.read" not in permissions and "auth.telegram" not in permissions:
        raise HTTPException(403, "forbidden")
    _tenant(claims, tenant_id)
    rows = (
        await db.scalars(
            select(Product)
            .where(Product.tenant_id == tenant_id, Product.active.is_(True))
            .order_by(Product.id)
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
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    permissions = claims.get("permissions", [])
    if "products.read" not in permissions and "auth.telegram" not in permissions:
        raise HTTPException(403, "forbidden")
    _tenant(claims, tenant_id)
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.active.is_(True),
        )
    )
    if not product:
        raise HTTPException(404, "product_not_found")
    plans = (
        await db.scalars(
            select(Plan)
            .where(Plan.product_id == product.id, Plan.active.is_(True))
            .order_by(Plan.price)
        )
    ).all()
    response = []
    for plan in plans:
        pricing = calculate_price(
            plan.price,
            plan.discount_kind or "none",
            plan.discount_value or 0,
        )
        response.append(
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
    return response


@r.post("/products")
async def create_product_route(
    x: ProductCreate,
    tenant_id: int,
    claims=Depends(require_permission("products.write")),
    db: AsyncSession = Depends(get_db),
):
    _tenant(claims, tenant_id)
    try:
        product = await create_product(
            db=db,
            tenant_id=tenant_id,
            name=x.name,
            description=x.description,
            category=x.category,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "active": product.active,
    }


@r.post("/plans")
async def create_plan_route(
    x: PlanCreate,
    product_id: int,
    tenant_id: int,
    claims=Depends(require_permission("products.write")),
    db: AsyncSession = Depends(get_db),
):
    _tenant(claims, tenant_id)
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
        )
    )
    if not product:
        raise HTTPException(404, "product_not_found")
    try:
        plan = await create_plan(
            db=db,
            tenant_id=tenant_id,
            product_id=product_id,
            name=x.name,
            price=x.price,
            duration_days=x.duration_days,
            quota_gb=x.quota_gb,
            discount_kind=getattr(x, "discount_kind", "none"),
            discount_value=getattr(x, "discount_value", 0),
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    return {
        "id": plan.id,
        "name": plan.name,
        "price": str(plan.price),
        "duration_days": plan.duration_days,
        "quota_gb": plan.quota_gb,
        "active": plan.active,
    }
