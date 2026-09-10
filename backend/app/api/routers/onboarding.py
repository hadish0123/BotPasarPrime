from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer
from app.api.schemas import OnboardingCreate, OnboardingPaymentSubmit
from app.core.config import settings
from app.core.db import get_db
from app.models.onboarding import OnboardingPayment
from app.services.onboarding import activation_fee, create_onboarding, submit_activation_payment

r = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _manual_payment_details(path: str) -> dict:
    fee = activation_fee(path)
    if fee <= 0:
        return {"method": "none", "amount_toman": 0}
    return {
        "method": "card_to_card",
        "amount_toman": fee,
        "card_number": settings.manual_payment_card_number,
        "card_holder": settings.manual_payment_card_holder,
        "bank": settings.manual_payment_bank or None,
    }


@r.post("")
async def register_tenant(payload: OnboardingCreate, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    user_id = claims.get("user_id") or claims.get("sub")
    telegram_id = claims.get("telegram_id")
    if not user_id or not telegram_id:
        raise HTTPException(401, "telegram_identity_required")
    path = "primevpn_representative" if payload.path == "representative" else payload.path
    try:
        tenant, approval = await create_onboarding(db, telegram_id=int(telegram_id), username=claims.get("username"), first_name=claims.get("first_name"), slug=payload.slug, name=payload.name, path=path, api_token=payload.pasarguard_api_token, login_url=payload.pasarguard_url, pasarguard_username=payload.pasarguard_username or "", submitted_telegram_id=int(telegram_id), bot_token=payload.bot_token, idempotency_key=payload.idempotency_key, bot_name=payload.bot_name)
        payment = await db.scalar(select(OnboardingPayment).where(OnboardingPayment.tenant_id == tenant.id).order_by(OnboardingPayment.id.desc()))
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
        "configured_activation_fee_toman": int(settings.activation_fee_toman),
        "activation_payment_id": payment.id if payment else None,
        "activation_payment_status": payment.status if payment else "not_required",
        "manual_payment": _manual_payment_details(approval.path),
        "pasarguard_health": "verified",
    }


@r.post("/payments/{payment_id}/submit")
async def submit_activation_payment_api(payment_id: int, payload: OnboardingPaymentSubmit, claims=Depends(bearer), db: AsyncSession = Depends(get_db)):
    telegram_id = claims.get("telegram_id")
    if not telegram_id:
        raise HTTPException(401, "telegram_identity_required")
    try:
        payment = await submit_activation_payment(db, payment_id=payment_id, telegram_id=int(telegram_id), reference=payload.reference)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None
    return {"id": payment.id, "tenant_id": payment.tenant_id, "amount": str(payment.amount), "status": payment.status}
