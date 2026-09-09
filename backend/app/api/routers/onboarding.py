from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer
from app.api.schemas import OnboardingCreate, OnboardingPaymentSubmit
from app.core.db import get_db
from app.core.config import settings
from app.services.onboarding import activation_fee, create_onboarding, submit_activation_payment

r = APIRouter(prefix="/onboarding", tags=["onboarding"])


@r.post("")
async def register_tenant(
    payload: OnboardingCreate,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    user_id = claims.get("user_id") or claims.get("sub")
    telegram_id = claims.get("telegram_id")
    if not user_id or not telegram_id:
        raise HTTPException(401, "telegram_identity_required")
    try:
        tenant, approval = await create_onboarding(
            db,
            telegram_id=int(telegram_id),
            username=claims.get("username"),
            first_name=claims.get("first_name"),
            slug=payload.slug,
            name=payload.name,
            path=payload.path,
            api_token=payload.pasarguard_api_token,
            login_url=payload.pasarguard_url,
            pasarguard_username=payload.pasarguard_username or "",
            submitted_telegram_id=int(telegram_id),
            bot_token=payload.bot_token,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    return {
        "tenant_id": tenant.id,
        "approval_id": approval.id,
        "status": tenant.status,
        "path": approval.path,
        "activation_fee_toman": activation_fee(approval.path),
        "pasarguard_health": "verified",
        "configured_activation_fee_toman": int(settings.activation_fee_toman),
    }


@r.post("/payments/{payment_id}/submit")
async def submit_activation_payment_api(
    payment_id: int,
    payload: OnboardingPaymentSubmit,
    claims=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    telegram_id = claims.get("telegram_id")
    if not telegram_id:
        raise HTTPException(401, "telegram_identity_required")
    try:
        payment = await submit_activation_payment(
            db,
            payment_id=payment_id,
            telegram_id=int(telegram_id),
            reference=payload.reference,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    return {
        "id": payment.id,
        "tenant_id": payment.tenant_id,
        "amount": str(payment.amount),
        "status": payment.status,
    }
