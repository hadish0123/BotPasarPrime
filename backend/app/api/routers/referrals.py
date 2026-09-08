from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.referrals import (
    create_commission_ledger,
    create_referral,
    get_referral_by_code,
    list_commission_ledger,
)

router = APIRouter(
    prefix="/referrals",
    tags=["referrals"],
)


@router.post("")
async def register_referral(
    tenant_id: int,
    referrer_user_id: int,
    referred_user_id: int,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        referral = await create_referral(
            db,
            tenant_id,
            referrer_user_id,
            referred_user_id,
            code,
        )
        await db.commit()

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None

    return {
        "id": referral.id,
        "tenant_id": referral.tenant_id,
        "inviter_user_id": referral.inviter_user_id,
        "invited_user_id": referral.invited_user_id,
        "code": referral.code,
    }


@router.get("/{code}")
async def referral(
    code: str,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
):
    referral = await get_referral_by_code(
        db,
        tenant_id,
        code,
    )

    if not referral:
        raise HTTPException(
            status_code=404,
            detail="referral_not_found",
        )

    return {
        "tenant_id": referral.tenant_id,
        "inviter_user_id": referral.inviter_user_id,
        "invited_user_id": referral.invited_user_id,
        "code": referral.code,
    }


@router.get("")
async def commission_ledger(
    tenant_id: int,
    user_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    rows = await list_commission_ledger(
        db,
        tenant_id,
        user_id,
    )

    return [
        {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "referral_id": row.referral_id,
            "order_id": row.order_id,
            "user_id": row.user_id,
            "amount": str(row.amount),
            "commission_percent": str(row.commission_percent),
            "ledger_type": row.ledger_type,
            "created_at": (row.created_at.isoformat() if row.created_at else None),
        }
        for row in rows
    ]


@router.post("/ledger")
async def add_commission_ledger(
    tenant_id: int,
    referral_id: int,
    user_id: int,
    amount: float,
    commission_percent: float,
    idempotency_key: str,
    order_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        ledger = await create_commission_ledger(
            db=db,
            tenant_id=tenant_id,
            referral_id=referral_id,
            user_id=user_id,
            amount=amount,
            commission_percent=commission_percent,
            idempotency_key=idempotency_key,
            order_id=order_id,
        )

        await db.commit()

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from None

    return {
        "id": ledger.id,
        "tenant_id": ledger.tenant_id,
        "referral_id": ledger.referral_id,
        "order_id": ledger.order_id,
        "user_id": ledger.user_id,
        "amount": str(ledger.amount),
        "commission_percent": str(ledger.commission_percent),
        "ledger_type": ledger.ledger_type,
    }


# Compatibility export used by app.main
r = router
