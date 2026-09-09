from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import (
    ApprovalRequest,
    BotInstance,
    Tenant,
    TenantBranding,
    TenantCredential,
    TenantSettings,
    TenantUser,
    User,
)
from app.models.onboarding import OnboardingPayment
from app.pasarguard.base import PasarGuardCredentials
from app.pasarguard.client import PasarGuardClient
from app.security.crypto import box

VALID_PATHS = {"primevpn_representative", "personal_panel"}


def normalize_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        raise ValueError("invalid tenant slug")
    return value[:80]


def validate_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("https://", "http://")):
        raise ValueError("invalid login url")
    return value


def validate_bot_token(value: str) -> str:
    value = value.strip()
    if ":" not in value or len(value) < 30:
        raise ValueError("invalid bot token")
    return value


async def _credential(db: AsyncSession, tenant_id: int, kind: str, value: str) -> None:
    db.add(
        TenantCredential(
            tenant_id=tenant_id,
            kind=kind,
            encrypted_value=box.encrypt(value),
            masked_value=box.mask(value),
        )
    )


async def get_user(
    db: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        db.add(user)
        await db.flush()
    else:
        user.username = username
        user.first_name = first_name
    return user


async def create_onboarding(
    db: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    slug: str,
    name: str,
    path: str,
    api_token: str,
    login_url: str,
    pasarguard_username: str,
    submitted_telegram_id: int,
    bot_token: str,
) -> tuple[Tenant, ApprovalRequest]:
    if path not in VALID_PATHS:
        raise ValueError("invalid onboarding path")
    if submitted_telegram_id != telegram_id:
        raise ValueError("telegram id mismatch")

    api_token = api_token.strip()
    login_url = validate_url(login_url)
    pasarguard_username = pasarguard_username.strip()
    bot_token = validate_bot_token(bot_token)
    if len(api_token) < 8:
        raise ValueError("invalid api token")
    if not pasarguard_username:
        raise ValueError("pasarguard username is required")

    slug = normalize_slug(slug)
    name = name.strip()
    if not name:
        raise ValueError("tenant name is required")

    existing = await db.execute(
        select(Tenant).where(Tenant.slug == slug, Tenant.is_deleted.is_(False))
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("tenant slug already exists")

    credentials = PasarGuardCredentials(
        base_url=login_url,
        api_token=api_token,
        username=pasarguard_username,
    )
    health = await PasarGuardClient(
        credentials,
        timeout_seconds=settings.pasarguard_timeout_seconds,
    ).health()
    if not health.ok:
        raise ValueError("PasarGuard health check failed")

    user = await get_user(
        db,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
    )

    tenant = Tenant(
        slug=slug,
        name=name,
        status=("pending_review" if path == "primevpn_representative" else "awaiting_payment"),
    )
    db.add(tenant)
    await db.flush()

    fee = activation_fee(path)
    db.add(
        TenantSettings(
            tenant_id=tenant.id,
            settings={
                "onboarding_path": path,
                "activation_fee_toman": fee,
                "payment_status": "not_required" if fee == 0 else "unpaid",
                "pasarguard_health": "verified",
            },
        )
    )
    db.add(TenantBranding(tenant_id=tenant.id, display_name=name))
    db.add(
        TenantUser(
            tenant_id=tenant.id,
            user_id=user.id,
            status="pending",
            role="tenant_owner",
        )
    )

    await _credential(db, tenant.id, "pasarguard_api_token", api_token)
    await _credential(db, tenant.id, "pasarguard_login_url", login_url)
    await _credential(db, tenant.id, "pasarguard_username", pasarguard_username)
    await _credential(db, tenant.id, "owner_telegram_id", str(submitted_telegram_id))
    await _credential(db, tenant.id, "bot_token", bot_token)

    db.add(
        BotInstance(
            tenant_id=tenant.id,
            name=name,
            encrypted_token=box.encrypt(bot_token),
            masked_token=box.mask(bot_token),
            status="pending",
        )
    )

    if fee:
        db.add(
            OnboardingPayment(
                tenant_id=tenant.id,
                user_id=user.id,
                amount=fee,
                provider="manual",
                status="awaiting_payment",
                idempotency_key=f"onboarding:{tenant.id}",
            )
        )

    approval = ApprovalRequest(
        tenant_id=tenant.id,
        path=path,
        status="pending_review" if fee == 0 else "awaiting_payment",
    )
    db.add(approval)
    await db.flush()
    return tenant, approval


async def submit_activation_payment(
    db: AsyncSession,
    *,
    payment_id: int,
    telegram_id: int,
    reference: str,
) -> OnboardingPayment:
    reference = reference.strip()
    if not reference:
        raise ValueError("payment reference is required")
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        raise ValueError("user not found")
    payment = await db.scalar(
        select(OnboardingPayment).where(
            OnboardingPayment.id == payment_id,
            OnboardingPayment.user_id == user.id,
        )
    )
    if payment is None:
        raise ValueError("onboarding payment not found")
    if payment.status != "awaiting_payment":
        raise ValueError("onboarding payment is not awaiting payment")
    payment.reference = reference
    payment.status = "submitted"

    approval = await db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == payment.tenant_id,
            ApprovalRequest.status == "awaiting_payment",
        )
    )
    if approval:
        approval.status = "pending_review"
    tenant = await db.get(Tenant, payment.tenant_id)
    if tenant:
        tenant.status = "pending_review"
    settings_row = await db.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == payment.tenant_id)
    )
    if settings_row:
        settings_row.settings = {
            **(settings_row.settings or {}),
            "payment_status": "submitted",
        }
    await db.flush()
    return payment


def activation_fee(path: str) -> int:
    if path == "personal_panel":
        return int(settings.activation_fee_toman)
    return 0
