from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Wallet, WalletTransaction
from app.wallet_coupon_referral_contract import money


async def get_or_create_wallet(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
):
    wallet = await db.scalar(
        select(Wallet)
        .where(
            Wallet.tenant_id == tenant_id,
            Wallet.user_id == user_id,
        )
        .with_for_update()
    )

    if wallet:
        return wallet

    wallet = Wallet(
        tenant_id=tenant_id,
        user_id=user_id,
        balance=Decimal("0.00"),
    )
    db.add(wallet)
    await db.flush()
    return wallet


async def post_wallet_transaction(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
    amount,
    direction: str,
    reason: str,
    idempotency_key: str,
):
    amount = money(amount)

    if amount <= 0:
        raise ValueError("wallet transaction amount must be positive")

    if direction not in {"credit", "debit"}:
        raise ValueError("invalid wallet direction")

    if not idempotency_key or len(idempotency_key) > 100:
        raise ValueError("invalid wallet idempotency key")

    existing = await db.scalar(
        select(WalletTransaction).where(
            WalletTransaction.idempotency_key == idempotency_key
        )
    )

    if existing:
        return existing

    wallet = await get_or_create_wallet(db, tenant_id, user_id)

    if wallet.tenant_id != tenant_id or wallet.user_id != user_id:
        raise ValueError("wallet tenant mismatch")

    current_balance = money(wallet.balance)
    if direction == "debit" and current_balance < amount:
        raise ValueError("insufficient wallet balance")

    wallet.balance = (
        current_balance + amount
        if direction == "credit"
        else current_balance - amount
    )

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        direction=direction,
        reason=reason,
        idempotency_key=idempotency_key,
    )

    db.add(transaction)
    await db.flush()

    return transaction
