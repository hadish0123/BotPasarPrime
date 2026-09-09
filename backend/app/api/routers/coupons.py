from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_tenant_match
from app.core.db import get_db
from app.services.coupons import calculate_coupon_for_order
from app.wallet_coupon_referral_contract import money

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.post("/validate")
async def validate_coupon(
    tenant_id: int,
    code: str,
    subtotal: float,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    try:
        coupon, discount = await calculate_coupon_for_order(
            db,
            tenant_id,
            code,
            subtotal,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None

    return {
        "code": coupon.code,
        "discount": str(money(discount)),
        "subtotal": str(money(subtotal)),
        "total": str(money(subtotal) - money(discount)),
    }


r = router
