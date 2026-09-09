from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Referral, ReferralTransaction, TenantSettings
from app.services.wallet import post_wallet_transaction
from app.wallet_coupon_referral_contract import calculate_commission, money, validate_referral


async def get_referral_by_code(db: AsyncSession, tenant_id: int, code: str):
    return await db.scalar(select(Referral).where(Referral.tenant_id == tenant_id, Referral.code == code.strip().upper()))


async def create_referral(db: AsyncSession, tenant_id: int, referrer_user_id: int, referred_user_id: int, code: str):
    validate_referral(referrer_user_id, referred_user_id)
    code = code.strip().upper()
    if not code or len(code) > 60:
        raise ValueError("invalid referral code")
    existing_user = await db.scalar(select(Referral).where(Referral.tenant_id == tenant_id, Referral.invited_user_id == referred_user_id))
    if existing_user:
        return existing_user
    if await db.scalar(select(Referral).where(Referral.tenant_id == tenant_id, Referral.code == code)):
        raise ValueError("referral_code_already_exists")
    referral = Referral(tenant_id=tenant_id, inviter_user_id=referrer_user_id, invited_user_id=referred_user_id, code=code)
    db.add(referral)
    await db.flush()
    return referral


async def calculate_referral_commission(amount, commission_percent):
    return calculate_commission(amount, commission_percent)


async def create_commission_ledger(db: AsyncSession, tenant_id: int, referral_id: int, user_id: int, amount, commission_percent, idempotency_key: str, order_id: int | None = None):
    amount = money(amount)
    percent = Decimal(str(commission_percent))
    if amount <= 0:
        raise ValueError("commission amount must be positive")
    if percent < 0 or percent > 100:
        raise ValueError("invalid commission percentage")
    if not idempotency_key or len(idempotency_key) > 120:
        raise ValueError("invalid commission idempotency key")
    referral = await db.scalar(select(Referral).where(Referral.id == referral_id, Referral.tenant_id == tenant_id))
    if not referral:
        raise ValueError("referral_not_found")
    if referral.inviter_user_id != user_id:
        raise ValueError("referral_user_mismatch")
    existing = await db.scalar(select(ReferralTransaction).where(ReferralTransaction.idempotency_key == idempotency_key))
    if existing:
        if existing.tenant_id != tenant_id:
            raise ValueError("cross_tenant_ledger_access")
        return existing
    ledger = ReferralTransaction(referral_id=referral.id, tenant_id=tenant_id, order_id=order_id, user_id=user_id, amount=amount, commission_percent=percent, ledger_type="commission", idempotency_key=idempotency_key)
    db.add(ledger)
    await db.flush()
    await post_wallet_transaction(db, tenant_id=tenant_id, user_id=user_id, amount=amount, direction="credit", reason=f"referral:{referral.id}", idempotency_key=f"referral-wallet:{idempotency_key}")
    return ledger


async def award_commission_for_order(db: AsyncSession, *, tenant_id: int, order_id: int, referred_user_id: int, order_amount) -> ReferralTransaction | None:
    referral = await db.scalar(select(Referral).where(Referral.tenant_id == tenant_id, Referral.invited_user_id == referred_user_id))
    if referral is None:
        return None
    tenant_settings = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
    percent = Decimal(str((tenant_settings.settings or {}).get("referral_percent", "0") if tenant_settings else "0"))
    if percent <= 0:
        return None
    commission = money(calculate_commission(order_amount, percent))
    return await create_commission_ledger(db, tenant_id, referral.id, referral.inviter_user_id, commission, percent, f"order:{order_id}:referral", order_id=order_id)


async def list_commission_ledger(db: AsyncSession, tenant_id: int, user_id: int | None = None):
    stmt = select(ReferralTransaction).where(ReferralTransaction.tenant_id == tenant_id, ReferralTransaction.ledger_type == "commission")
    if user_id is not None:
        stmt = stmt.where(ReferralTransaction.user_id == user_id)
    return list((await db.scalars(stmt.order_by(ReferralTransaction.id.desc()))).all())
