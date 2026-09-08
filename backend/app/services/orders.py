from __future__ import annotations

from app.services.shop import create_order_from_plan


async def create_order(
    db,
    tenant_id,
    user_id,
    plan_id,
    unit_price=None,
    key=None,
):
    """
    Backward-compatible wrapper.

    The actual price is ALWAYS calculated from the current
    Tenant-owned Plan and its pricing rules. A caller supplied
    unit_price is intentionally ignored.
    """
    return await create_order_from_plan(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        plan_id=plan_id,
        key=key,
    )
