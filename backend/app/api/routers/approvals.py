from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ApprovalAction
from app.core.db import get_db
from app.models.entities import ApprovalRequest, Tenant
from app.services.approvals import review_approval

r = APIRouter(prefix="/approvals", tags=["approvals"])


@r.get("")
async def list_approvals(
    status: str | None = "pending_review",
    db: AsyncSession = Depends(get_db),
):
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())

    if status:
        query = query.where(ApprovalRequest.status == status)

    result = await db.execute(query)
    rows = result.scalars().all()

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
        for x in rows
    ]


@r.get("/{approval_id}")
async def get_approval(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
):
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
    reviewer_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        approval = await review_approval(
            db,
            approval_id=approval_id,
            approved=x.approved,
            reviewer_id=reviewer_id,
            note=x.note,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc

    return {
        "id": approval.id,
        "status": approval.status,
        "tenant_id": approval.tenant_id,
    }
