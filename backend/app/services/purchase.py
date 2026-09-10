from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    Order,
    OrderItem,
    Payment,
    Plan,
    Service,
    TenantCredential,
    TenantSettings,
    User,
)
from app.pasarguard.base import PasarGuardCredentials
from app.pasarguard.client import PasarGuardClient
from app.security.crypto import box
from app.services.audit import audit_sensitive
from app.services.payments import create_payment, transition
from app.services.shop import build_plan_snapshot, create_order_from_plan
from app.services.wallet import post_wallet_transaction


async def _credentials(db: AsyncSession, tenant_id: int) -> PasarGuardCredentials:
    rows = (
        await db.scalars(
            select(TenantCredential).where(TenantCredential.tenant_id == tenant_id)
        )
    ).all()
    values = {row.kind: box.decrypt(row.encrypted_value) for row in rows}
    base_url = values.get("pasarguard_login_url")
    api_token = values.get("pasarguard_api_token")
    username = values.get("pasarguard_username")
    if not base_url or not api_token:
        raise ValueError("pasarguard_credentials_missing")
    return PasarGuardCredentials(base_url=base_url, api_token=api_token, username=username)


async def _group_ids(db: AsyncSession, tenant_id: int) -> list[int]:
    settings = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
    configured = (settings.settings or {}).get("pasarguard_group_ids") if settings else None
    if configured:
        ids = [int(value) for value in configured if int(value) > 0]
        if ids:
            return ids
    return [1]


async def _provision_service(
    db: AsyncSession,
    *,
    tenant_id: int,
    user: User,
    order: Order,
    plan: Plan,
) -> Service:
    existing = (
        await db.scalars(
            select(Service).where(Service.tenant_id == tenant_id, Service.user_id == user.id)
        )
    ).all()
    for service in existing:
        if service.metadata_json.get("order_id") == order.id:
            return service

    credentials = await _credentials(db, tenant_id)
    client = PasarGuardClient(credentials)
    username = f"tg_{user.telegram_id}_{order.id}"
    payload = {
        "username": username,
        "group_ids": await _group_ids(db, tenant_id),
        "status": "active",
        "data_limit": int(plan.quota_gb or 0) * 1024 * 1024 * 1024,
        "expire_duration": int(plan.duration_days or 0) * 86400,
        "note": f"3XSHOP order #{order.id}",
    }

    remote = None
    try:
        remote = await client.create_user(payload)
        external_id = str(remote.get("id") or remote.get("username") or username)
        subscription_url = remote.get("subscription_url")
        if not subscription_url:
            subscription = await client.get_subscription(external_id)
            if isinstance(subscription, dict):
                subscription_url = subscription.get("subscription_url")
                remote = {**remote, **subscription}
        if not subscription_url:
            raise ValueError("pasarguard_subscription_not_returned")

        expires_at = datetime.now(UTC) + timedelta(days=plan.duration_days) if plan.duration_days else None
        service = Service(
            tenant_id=tenant_id,
            user_id=user.id,
            external_id=external_id,
            status="active",
            expires_at=expires_at,
            metadata_json={
                "order_id": order.id,
                "plan_id": plan.id,
                "username": username,
                "subscription_url": subscription_url,
            },
        )
        db.add(service)
        await db.flush()
        return service
    except Exception:
        if remote:
            try:
                await client.delete_user(str(remote.get("id") or remote.get("username") or username))
            except Exception:
                pass
        raise


async def purchase_with_wallet(
    db: AsyncSession,
    *,
    tenant_id: int,
    user: User,
    plan_id: int,
    idempotency_key: str,
) -> tuple[Order, Payment, Service]:
    order = await create_order_from_plan(db, tenant_id, user.id, plan_id, idempotency_key)
    payment = await create_payment(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        amount=order.total,
        provider="wallet",
        key=f"wallet:{idempotency_key}",
    )
    if payment.status == "created":
        transition(payment, "awaiting_payment")

    await post_wallet_transaction(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        amount=order.total,
        direction="debit",
        reason=f"purchase:{order.id}",
        idempotency_key=f"purchase:{tenant_id}:{order.id}",
    )
    transition(payment, "paid")
    order.status = "completed"

    plan, _, _, _ = await build_plan_snapshot(db, tenant_id, plan_id)
    service = await _provision_service(
        db, tenant_id=tenant_id, user=user, order=order, plan=plan
    )
    audit_sensitive(
        db,
        action="service.create",
        tenant_id=tenant_id,
        actor_type="user",
        actor_id=user.id,
        target_type="service",
        target_id=service.id,
        metadata={"order_id": order.id, "plan_id": plan.id},
    )
    await db.flush()
    return order, payment, service


async def create_direct_payment(
    db: AsyncSession,
    *,
    tenant_id: int,
    user: User,
    plan_id: int,
    idempotency_key: str,
) -> tuple[Order, Payment]:
    order = await create_order_from_plan(db, tenant_id, user.id, plan_id, idempotency_key)
    payment = await create_payment(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        amount=order.total,
        provider="manual",
        key=f"direct:{idempotency_key}",
    )
    if payment.status == "created":
        transition(payment, "awaiting_payment")
    return order, payment


async def fulfill_verified_payment(
    db: AsyncSession,
    *,
    tenant_id: int,
    payment_id: int,
) -> Service:
    payment = await db.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.tenant_id == tenant_id)
    )
    if not payment or payment.status != "paid":
        raise ValueError("payment_not_paid")
    order = await db.scalar(
        select(Order).where(Order.id == payment.order_id, Order.tenant_id == tenant_id)
    )
    if not order:
        raise ValueError("order_not_found")
    user = await db.get(User, order.user_id)
    item = await db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    if not user or not item:
        raise ValueError("purchase_data_missing")
    plan, _, _, _ = await build_plan_snapshot(db, tenant_id, item.plan_id)
    service = await _provision_service(
        db, tenant_id=tenant_id, user=user, order=order, plan=plan
    )
    order.status = "completed"
    await db.flush()
    return service
