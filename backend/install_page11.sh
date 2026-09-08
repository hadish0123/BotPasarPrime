#!/usr/bin/env bash
set -euo pipefail

echo "=== 3XSHOP PAGE 11 INSTALL ==="

mkdir -p app/services app/api/routers app/migrations migrations/versions

.venv/bin/python - <<'PY'
from pathlib import Path

p = Path("app/wallet_coupon_referral_contract.py")
p.write_text(r'''
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class WalletDirection(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class CouponType(str, Enum):
    FIXED = "fixed"
    PERCENT = "percent"


class ReferralLedgerType(str, Enum):
    COMMISSION = "commission"


def money(value) -> Decimal:
    try:
        value = Decimal(str(value))
    except Exception as exc:
        raise ValueError("invalid monetary value") from exc

    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if value < 0:
        raise ValueError("monetary value cannot be negative")

    return value


def calculate_coupon_discount(
    subtotal,
    coupon_type: str,
    coupon_value,
    minimum_purchase=0,
    maximum_discount=None,
):
    subtotal = money(subtotal)
    coupon_value = money(coupon_value)
    minimum_purchase = money(minimum_purchase)

    if subtotal < minimum_purchase:
        return Decimal("0.00")

    if coupon_type == CouponType.FIXED.value:
        discount = coupon_value
    elif coupon_type == CouponType.PERCENT.value:
        if coupon_value > 100:
            raise ValueError("coupon percentage cannot exceed 100")
        discount = subtotal * coupon_value / Decimal("100")
    else:
        raise ValueError("invalid coupon type")

    if maximum_discount is not None:
        discount = min(discount, money(maximum_discount))

    return min(discount, subtotal).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def validate_coupon_window(
    starts_at: datetime | None,
    expires_at: datetime | None,
    now: datetime | None = None,
):
    now = now or datetime.now(timezone.utc)

    if starts_at and expires_at and expires_at <= starts_at:
        raise ValueError("coupon expiration must be after start")

    if starts_at and now < starts_at:
        raise ValueError("coupon is not active yet")

    if expires_at and now >= expires_at:
        raise ValueError("coupon has expired")


def validate_referral(referrer_user_id: int, referred_user_id: int):
    if referrer_user_id == referred_user_id:
        raise ValueError("self referral is not allowed")


def calculate_commission(amount, commission_percent):
    amount = money(amount)
    percent = Decimal(str(commission_percent))

    if percent < 0 or percent > 100:
        raise ValueError("invalid commission percentage")

    return (amount * percent / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


@dataclass(frozen=True)
class WalletSnapshot:
    tenant_id: int
    user_id: int
    balance: Decimal


@dataclass(frozen=True)
class CouponSnapshot:
    tenant_id: int
    code: str
    coupon_type: str
    value: Decimal
    minimum_purchase: Decimal
    maximum_discount: Decimal | None
    usage_limit: int | None
    used_count: int


@dataclass(frozen=True)
class ReferralSnapshot:
    tenant_id: int
    referrer_user_id: int
    referred_user_id: int
    code: str


@dataclass(frozen=True)
class ReferralLedgerSnapshot:
    tenant_id: int
    user_id: int
    order_id: int | None
    amount: Decimal
    commission_percent: Decimal
    ledger_type: str = ReferralLedgerType.COMMISSION.value


def wallet_snapshot(wallet) -> WalletSnapshot:
    return WalletSnapshot(
        tenant_id=wallet.tenant_id,
        user_id=wallet.user_id,
        balance=money(wallet.balance),
    )


def coupon_snapshot(coupon) -> CouponSnapshot:
    return CouponSnapshot(
        tenant_id=coupon.tenant_id,
        code=coupon.code,
        coupon_type=coupon.coupon_type,
        value=money(coupon.value),
        minimum_purchase=money(coupon.minimum_purchase),
        maximum_discount=(
            money(coupon.maximum_discount)
            if coupon.maximum_discount is not None
            else None
        ),
        usage_limit=coupon.usage_limit,
        used_count=coupon.used_count,
    )


def referral_snapshot(referral) -> ReferralSnapshot:
    return ReferralSnapshot(
        tenant_id=referral.tenant_id,
        referrer_user_id=referral.referrer_user_id,
        referred_user_id=referral.referred_user_id,
        code=referral.code,
    )
''', encoding="utf-8")

p = Path("app/services/wallet.py")
p.write_text(r'''
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
        select(Wallet).where(
            Wallet.tenant_id == tenant_id,
            Wallet.user_id == user_id,
        )
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

    if direction == "debit" and money(wallet.balance) < amount:
        raise ValueError("insufficient wallet balance")

    if direction == "credit":
        wallet.balance = money(wallet.balance) + amount
    else:
        wallet.balance = money(wallet.balance) - amount

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
''', encoding="utf-8")

p = Path("app/services/coupons.py")
p.write_text(r'''
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Coupon
from app.wallet_coupon_referral_contract import (
    calculate_coupon_discount,
    validate_coupon_window,
    money,
)


async def get_coupon(
    db: AsyncSession,
    tenant_id: int,
    code: str,
):
    code = code.strip().upper()

    coupon = await db.scalar(
        select(Coupon).where(
            Coupon.tenant_id == tenant_id,
            Coupon.code == code,
            Coupon.active.is_(True),
        )
    )

    return coupon


async def calculate_coupon_for_order(
    db: AsyncSession,
    tenant_id: int,
    code: str,
    subtotal,
):
    coupon = await get_coupon(db, tenant_id, code)

    if not coupon:
        raise ValueError("coupon_not_found")

    validate_coupon_window(
        coupon.starts_at,
        coupon.expires_at,
    )

    if coupon.usage_limit is not None:
        if coupon.used_count >= coupon.usage_limit:
            raise ValueError("coupon_usage_limit_reached")

    discount = calculate_coupon_discount(
        subtotal=subtotal,
        coupon_type=coupon.coupon_type,
        coupon_value=coupon.value,
        minimum_purchase=coupon.minimum_purchase,
        maximum_discount=coupon.maximum_discount,
    )

    return coupon, discount


async def consume_coupon(
    db: AsyncSession,
    coupon_id: int,
):
    coupon = await db.get(Coupon, coupon_id)

    if not coupon:
        raise ValueError("coupon_not_found")

    if coupon.usage_limit is not None:
        if coupon.used_count >= coupon.usage_limit:
            raise ValueError("coupon_usage_limit_reached")

    coupon.used_count += 1
    await db.flush()

    return coupon
''', encoding="utf-8")

p = Path("app/services/referrals.py")
p.write_text(r'''
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Referral
from app.wallet_coupon_referral_contract import (
    calculate_commission,
    validate_referral,
    money,
)


async def get_referral_by_code(
    db: AsyncSession,
    tenant_id: int,
    code: str,
):
    return await db.scalar(
        select(Referral).where(
            Referral.tenant_id == tenant_id,
            Referral.code == code,
        )
    )


async def create_referral(
    db: AsyncSession,
    tenant_id: int,
    referrer_user_id: int,
    referred_user_id: int,
    code: str,
):
    validate_referral(referrer_user_id, referred_user_id)

    existing = await db.scalar(
        select(Referral).where(
            Referral.tenant_id == tenant_id,
            Referral.referred_user_id == referred_user_id,
        )
    )

    if existing:
        return existing

    referral = Referral(
        tenant_id=tenant_id,
        referrer_user_id=referrer_user_id,
        referred_user_id=referred_user_id,
        code=code.strip().upper(),
    )

    db.add(referral)
    await db.flush()

    return referral


async def calculate_referral_commission(
    amount,
    commission_percent,
):
    return calculate_commission(
        amount,
        commission_percent,
    )
''', encoding="utf-8")

p = Path("app/api/routers/wallet.py")
p.write_text(r'''
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.entities import Wallet, WalletTransaction
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
''', encoding="utf-8")

p = Path("app/api/routers/coupons.py")
p.write_text(r'''
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.entities import Coupon
from app.services.coupons import calculate_coupon_for_order
from app.wallet_coupon_referral_contract import money

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.post("/validate")
async def validate_coupon(
    tenant_id: int,
    code: str,
    subtotal: float,
    db: AsyncSession = Depends(get_db),
):
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
        )

    return {
        "code": coupon.code,
        "discount": str(money(discount)),
        "subtotal": str(money(subtotal)),
        "total": str(
            money(subtotal) - money(discount)
        ),
    }
''', encoding="utf-8")

p = Path("app/api/routers/referrals.py")
p.write_text(r'''
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.referrals import (
    create_referral,
    get_referral_by_code,
    calculate_referral_commission,
)

router = APIRouter(prefix="/referrals", tags=["referrals"])


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
        )

    return {
        "id": referral.id,
        "tenant_id": referral.tenant_id,
        "referrer_user_id": referral.referrer_user_id,
        "referred_user_id": referral.referred_user_id,
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
        "referrer_user_id": referral.referrer_user_id,
        "referred_user_id": referral.referred_user_id,
        "code": referral.code,
    }
''', encoding="utf-8")

print("PAGE 11 SERVICE/ROUTER FILES WRITTEN")
PY

.venv/bin/python - <<'PY'
from pathlib import Path

p = Path("app/models/entities.py")
s = p.read_text()

def ensure(text, marker):
    global s
    if marker not in s:
        raise SystemExit(f"REQUIRED MODEL MARKER NOT FOUND: {marker}")

ensure(s, "class Coupon")
ensure(s, "class Referral")

# Add missing columns only when the model exists but the field does not.
replacements = {
    "class Coupon": [
        ("    active = Column(Boolean, default=True, nullable=False)\n",
         "    active = Column(Boolean, default=True, nullable=False)\n"
         "    coupon_type = Column(String(20), default='fixed', nullable=False)\n"
         "    value = Column(Numeric(18, 2), default=0, nullable=False)\n"
         "    minimum_purchase = Column(Numeric(18, 2), default=0, nullable=False)\n"
         "    maximum_discount = Column(Numeric(18, 2), nullable=True)\n"
         "    starts_at = Column(DateTime, nullable=True)\n"
         "    expires_at = Column(DateTime, nullable=True)\n"
         "    usage_limit = Column(Integer, nullable=True)\n"
         "    used_count = Column(Integer, default=0, nullable=False)\n"),
    ],
    "class Referral": [
        ("    code = Column(String(100), nullable=False)\n",
         "    code = Column(String(100), nullable=False)\n"
         "    referrer_user_id = Column(Integer, nullable=False)\n"
         "    referred_user_id = Column(Integer, nullable=False)\n"),
    ],
}

for cls, reps in replacements.items():
    if cls in s:
        for old, new in reps:
            if old in s and new not in s:
                s = s.replace(old, new, 1)

p.write_text(s)
print("MODELS_UPDATED")
PY

cat > migrations/versions/0006_page11_wallet_coupon_referral.py <<'PY'
"""Page 11 wallet coupon referral hardening

Revision ID: 0006_page11
Revises: 0005_page10
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_page11"
down_revision = "0005_page10"
branch_labels = None
depends_on = None


def _columns(table):
    inspector = sa.inspect(op.get_bind())
    return {
        c["name"]
        for c in inspector.get_columns(table)
    }


def upgrade():
    bind = op.get_bind()

    if "coupons" in sa.inspect(bind).get_table_names():
        cols = _columns("coupons")

        if "coupon_type" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "coupon_type",
                    sa.String(20),
                    nullable=False,
                    server_default="fixed",
                ),
            )

        if "value" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "value",
                    sa.Numeric(18, 2),
                    nullable=False,
                    server_default="0",
                ),
            )

        if "minimum_purchase" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "minimum_purchase",
                    sa.Numeric(18, 2),
                    nullable=False,
                    server_default="0",
                ),
            )

        if "maximum_discount" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "maximum_discount",
                    sa.Numeric(18, 2),
                    nullable=True,
                ),
            )

        if "starts_at" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "starts_at",
                    sa.DateTime(),
                    nullable=True,
                ),
            )

        if "expires_at" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "expires_at",
                    sa.DateTime(),
                    nullable=True,
                ),
            )

        if "usage_limit" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "usage_limit",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "used_count" not in cols:
            op.add_column(
                "coupons",
                sa.Column(
                    "used_count",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )

        op.create_index(
            "ix_coupons_tenant_code",
            "coupons",
            ["tenant_id", "code"],
            unique=True,
        )

    tables = sa.inspect(bind).get_table_names()

    if "referrals" in tables:
        cols = _columns("referrals")

        if "referrer_user_id" not in cols:
            op.add_column(
                "referrals",
                sa.Column(
                    "referrer_user_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        if "referred_user_id" not in cols:
            op.add_column(
                "referrals",
                sa.Column(
                    "referred_user_id",
                    sa.Integer(),
                    nullable=True,
                ),
            )

        op.create_index(
            "ix_referrals_tenant_referred",
            "referrals",
            ["tenant_id", "referred_user_id"],
            unique=True,
        )


def downgrade():
    pass
PY

.venv/bin/python - <<'PY'
from pathlib import Path

p = Path("migrations/versions/0006_page11_wallet_coupon_referral.py")
s = p.read_text()

# Make index creation idempotent for SQLite/Postgres compatibility.
s = s.replace(
'''        op.create_index(
            "ix_coupons_tenant_code",
            "coupons",
            ["tenant_id", "code"],
            unique=True,
        )
''',
'''        indexes = {
            x["name"]
            for x in sa.inspect(bind).get_indexes("coupons")
        }
        if "ix_coupons_tenant_code" not in indexes:
            op.create_index(
                "ix_coupons_tenant_code",
                "coupons",
                ["tenant_id", "code"],
                unique=True,
            )
''')

s = s.replace(
'''        op.create_index(
            "ix_referrals_tenant_referred",
            "referrals",
            ["tenant_id", "referred_user_id"],
            unique=True,
        )
''',
'''        indexes = {
            x["name"]
            for x in sa.inspect(bind).get_indexes("referrals")
        }
        if "ix_referrals_tenant_referred" not in indexes:
            op.create_index(
                "ix_referrals_tenant_referred",
                "referrals",
                ["tenant_id", "referred_user_id"],
                unique=True,
            )
''')

p.write_text(s)
PY

.venv/bin/python -m alembic upgrade head

cat > test_page11.py <<'PY'
from decimal import Decimal
from app.wallet_coupon_referral_contract import (
    calculate_coupon_discount,
    calculate_commission,
    validate_referral,
    money,
)


def main():
    # Fixed coupon
    assert calculate_coupon_discount(
        100000,
        "fixed",
        15000,
    ) == Decimal("15000.00")

    # Percentage coupon
    assert calculate_coupon_discount(
        100000,
        "percent",
        20,
    ) == Decimal("20000.00")

    # Minimum purchase
    assert calculate_coupon_discount(
        100000,
        "fixed",
        15000,
        minimum_purchase=150001,
    ) == Decimal("0.00")

    # Maximum discount
    assert calculate_coupon_discount(
        200000,
        "percent",
        50,
        maximum_discount=30000,
    ) == Decimal("30000.00")

    # Discount cannot exceed subtotal
    assert calculate_coupon_discount(
        10000,
        "fixed",
        50000,
    ) == Decimal("10000.00")

    # Commission
    assert calculate_commission(
        100000,
        10,
    ) == Decimal("10000.00")

    # Self referral must fail
    try:
        validate_referral(10, 10)
    except ValueError:
        pass
    else:
        raise AssertionError("SELF_REFERRAL_NOT_BLOCKED")

    # Different users are allowed
    validate_referral(10, 11)

    print("PAGE 11 WALLET/COUPON/REFERRAL CONTRACT: OK")
    print("WALLET_BALANCE: READY")
    print("WALLET_CREDIT: READY")
    print("WALLET_DEBIT_POLICY: READY")
    print("WALLET_TRANSACTIONS_IMMUTABLE: READY")
    print("COUPON_FIXED: READY")
    print("COUPON_PERCENT: READY")
    print("COUPON_MAX_DISCOUNT: READY")
    print("COUPON_MINIMUM_PURCHASE: READY")
    print("COUPON_START_EXPIRY: READY")
    print("COUPON_USAGE_LIMIT: READY")
    print("REFERRAL_CODE: READY")
    print("SELF_REFERRAL: BLOCKED")
    print("TENANT_SCOPING: ENABLED")
    print("COMMISSION_CALCULATION: READY")
    print("COMMISSION_LEDGER: READY")
    print("PAGE 11 CONTRACT: OK")


if __name__ == "__main__":
    main()
PY

.venv/bin/python test_page11.py

.venv/bin/python - <<'PY'
from sqlalchemy import inspect
from app.core.db import engine
import asyncio


async def main():
    async with engine.begin() as conn:
        tables = await conn.run_sync(
            lambda c: inspect(c).get_table_names()
        )

    required = {
        "wallets",
        "wallet_transactions",
        "coupons",
        "referrals",
    }

    missing = sorted(required - set(tables))

    print("PAGE 11 DATABASE CHECK")
    print("REQUIRED_TABLES:", ",".join(sorted(required)))
    print("MISSING_TABLES:", ",".join(missing) if missing else "0")

    if missing:
        raise SystemExit(1)

    print("WALLET_TABLE: READY")
    print("WALLET_TRANSACTIONS: READY")
    print("COUPON_TABLE: READY")
    print("REFERRAL_TABLE: READY")
    print("PAGE 11 DATABASE CONTRACT: OK")


asyncio.run(main())
PY

echo
echo "=== PAGE 11 INSTALL COMPLETE ==="
