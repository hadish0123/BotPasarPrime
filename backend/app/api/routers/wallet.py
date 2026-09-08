from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.wallet import get_or_create_wallet
from app.wallet_coupon_referral_contract import wallet_snapshot

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("")
async def wallet_balance(
    tenant_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    wallet = await get_or_create_wallet(
        db,
        tenant_id,
        user_id,
    )

    await db.commit()

    snapshot = wallet_snapshot(wallet)

    return {
        "tenant_id": snapshot.tenant_id,
        "user_id": snapshot.user_id,
        "balance": str(snapshot.balance),
    }


# Compatibility export used by app.main
r = router
