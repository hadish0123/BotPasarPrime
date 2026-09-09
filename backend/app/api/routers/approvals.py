from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.api.schemas import ApprovalAction
from app.bot.runtime import runtime
from app.core.db import get_db
from app.models.entities import ApprovalRequest, BotInstance, Tenant, TenantSettings
from app.models.onboarding import OnboardingPayment
from app.services.approvals import review_approval
from app.services.tenant_activation import activate_approved_tenant

r = APIRouter(prefix="/approvals", tags=["approvals"])


@r.get("")
async def list_approvals(
    status: str | None = "pending_review",
    claims=Depends(require_permission("tenants.approve")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "only platform owner can list approvals")
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status:
        query = query.where(ApprovalRequest.status == status)
    result = await db.execute(query)
    return [
        {
            "id": x.id,
            "tenant_id": x.tenant_id,
            "path": x.path,
            "status": x.status,
            "reviewer_id": x.reviewer_id,
            "note": x.note,
            "created_at": x.created_at,
        }
        for x in result.scalars().all()
    ]


@r.get("/onboarding-payments/pending")
async def pending_onboarding_payments(
    claims=Depends(require_permission("payments.verify")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "only platform owner can list onboarding payments")
    result = await db.execute(
        select(OnboardingPayment)
        .where(OnboardingPayment.status.in_(["submitted", "verifying"]))
        .order_by(OnboardingPayment.created_at.asc())
    )
    return [
        {
            "id": x.id,
            "tenant_id": x.tenant_id,
            "user_id": x.user_id,
            "amount": str(x.amount),
            "status": x.status,
            "reference": x.reference,
            "created_at": x.created_at,
        }
        for x in result.scalars().all()
    ]


@r.post("/onboarding-payments/{payment_id}/verify")
async def verify_onboarding_payment(
    payment_id: int,
    approve: bool = True,
    claims=Depends(require_permission("payments.verify")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "only platform owner can verify onboarding payments")
    payment = await db.get(OnboardingPayment, payment_id)
    if payment is None:
        raise HTTPException(404, "onboarding payment not found")
    if payment.status != "submitted":
        raise HTTPException(409, "onboarding payment is not awaiting verification")
    payment.status = "paid" if approve else "rejected"
    settings_row = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == payment.tenant_id)
    )
    if settings_row:
        settings_row.settings = {
            **(settings_row.settings or {}),
            "payment_status": payment.status,
        }
    await db.commit()
    return {"id": payment.id, "status": payment.status, "tenant_id": payment.tenant_id}


@r.get("/{approval_id}")
async def get_approval(
    approval_id: int,
    claims=Depends(require_permission("tenants.approve")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "forbidden")
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(404, "approval not found")
    tenant = await db.get(Tenant, approval.tenant_id)
    return {
        "id": approval.id,
        "tenant_id": approval.tenant_id,
        "path": approval.path,
        "status": approval.status,
        "reviewer_id": approval.reviewer_id,
        "note": approval.note,
        "created_at": approval.created_at,
        "tenant": {
            "id": tenant.id if tenant else None,
            "name": tenant.name if tenant else None,
            "slug": tenant.slug if tenant else None,
            "status": tenant.status if tenant else None,
        },
    }


@r.post("/{approval_id}")
async def act(
    approval_id: int,
    x: ApprovalAction,
    claims=Depends(require_permission("tenants.approve")),
    db: AsyncSession = Depends(get_db),
):
    if not claims.get("is_platform_owner"):
        raise HTTPException(403, "only platform owner can approve tenants")
    try:
        approval = await review_approval(
            db,
            approval_id=approval_id,
            approved=x.approved,
            reviewer_id=str(claims.get("sub")),
            note=x.note,
        )
        if x.approved:
            await activate_approved_tenant(db, approval.tenant_id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from None

    bot_status = None
    if x.approved:
        bot = await db.scalar(
            select(BotInstance).where(BotInstance.tenant_id == approval.tenant_id)
        )
        if bot is not None:
            try:
                await runtime.start_bot(bot)
            except RuntimeError:
                bot_status = "failed"
            else:
                bot_status = "running"

    return {
        "id": approval.id,
        "status": approval.status,
        "tenant_id": approval.tenant_id,
        "tenant_status": "active" if x.approved else "rejected",
        "bot_status": bot_status,
    }
