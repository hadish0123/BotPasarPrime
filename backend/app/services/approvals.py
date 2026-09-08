from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    ApprovalRequest,
    AuditLog,
    BotInstance,
    Tenant,
)

TRANSITIONS = {
    "draft": {"awaiting_payment", "pending_review", "rejected"},
    "awaiting_payment": {"pending_review", "rejected"},
    "pending_review": {"approved", "rejected"},
    "approved": {"active", "rejected"},
    "rejected": {"pending_review"},
    "active": set(),
}


def valid_transition(old: str, new: str) -> bool:
    return new in TRANSITIONS.get(old, set())


async def review_approval(
    db: AsyncSession,
    *,
    approval_id: int,
    approved: bool,
    reviewer_id: str,
    note: str | None = None,
) -> ApprovalRequest:
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id).with_for_update()
    )
    approval = result.scalar_one_or_none()

    if approval is None:
        raise ValueError("approval not found")

    if approval.status != "pending_review":
        raise ValueError("approval is not actionable")

    tenant = await db.get(Tenant, approval.tenant_id)

    if tenant is None or tenant.is_deleted:
        raise ValueError("tenant not found")

    target = "approved" if approved else "rejected"

    if not valid_transition(approval.status, target):
        raise ValueError("invalid approval transition")

    approval.status = target
    approval.reviewer_id = str(reviewer_id)
    approval.note = note

    if approved:
        tenant.status = "approved"

        result = await db.execute(select(BotInstance).where(BotInstance.tenant_id == tenant.id))
        bot = result.scalar_one_or_none()
        if bot:
            bot.status = "approved"
    else:
        tenant.status = "rejected"

        result = await db.execute(select(BotInstance).where(BotInstance.tenant_id == tenant.id))
        bot = result.scalar_one_or_none()
        if bot:
            bot.status = "rejected"

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_type="owner",
            actor_id=str(reviewer_id),
            action="onboarding.approved" if approved else "onboarding.rejected",
            target_type="approval_request",
            target_id=str(approval.id),
            metadata_json={
                "path": approval.path,
                "note": note,
            },
        )
    )

    await db.flush()
    return approval
