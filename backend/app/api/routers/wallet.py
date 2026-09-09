from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer, require_permission, require_tenant_match
from app.core.db import get_db
from app.models.entities import WalletTransaction
from app.services.audit import audit_sensitive
from app.services.wallet import get_or_create_wallet, post_wallet_transaction
from app.wallet_coupon_referral_contract import wallet_snapshot

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("")
async def wallet_balance(
    tenant_id: int,
    user_id: int | None = None,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    current_user = claims.get("user_id") or claims.get("sub")
    if not current_user:
        raise HTTPException(401, "user identity required")
    requested_user = int(user_id) if user_id is not None else int(current_user)
    if requested_user != int(current_user) and not claims.get("is_platform_owner"):
        if "wallet.read" not in claims.get("permissions", []):
            raise HTTPException(403, "forbidden")

    wallet = await get_or_create_wallet(db, tenant_id, requested_user)
    await db.commit()
    snapshot = wallet_snapshot(wallet)
    return {
        "tenant_id": snapshot.tenant_id,
        "user_id": snapshot.user_id,
        "balance": str(snapshot.balance),
    }


@router.get("/transactions")
async def wallet_transactions(
    tenant_id: int,
    user_id: int | None = None,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    current_user = int(claims.get("user_id") or claims.get("sub"))
    requested_user = int(user_id) if user_id is not None else current_user
    if requested_user != current_user and not claims.get("is_platform_owner"):
        if "wallet.read" not in claims.get("permissions", []):
            raise HTTPException(403, "forbidden")
    wallet = await get_or_create_wallet(db, tenant_id, requested_user)
    result = await db.execute(
        select(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": item.id,
            "amount": str(item.amount),
            "direction": item.direction,
            "reason": item.reason,
            "created_at": item.created_at,
        }
        for item in result.scalars().all()
    ]


@router.post("/transactions")
async def wallet_transaction(
    tenant_id: int,
    user_id: int,
    amount: str,
    direction: str,
    reason: str,
    idempotency_key: str,
    claims=Depends(require_permission("wallet.write")),
    db: AsyncSession = Depends(get_db),
):
    require_tenant_match(tenant_id, claims)
    try:
        transaction = await post_wallet_transaction(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            amount=amount,
            direction=direction,
            reason=reason.strip()[:80],
            idempotency_key=idempotency_key,
        )
        audit_sensitive(
            db,
            action="wallet.credit" if direction == "credit" else "wallet.debit",
            tenant_id=tenant_id,
            actor_type="admin",
            actor_id=claims.get("user_id") or claims.get("sub"),
            target_type="wallet",
            target_id=user_id,
            metadata={"amount": str(amount), "direction": direction, "reason": reason},
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    return {
        "id": transaction.id,
        "amount": str(transaction.amount),
        "direction": transaction.direction,
        "reason": transaction.reason,
    }


r = router
