"""
3XSHOP - Tenant Registration & Activation
==========================================

GitBook Page 3: ثبت و فعال‌سازی Tenant

Supported paths:

1. PRIMEVPN representative
   draft -> pending_review -> approved/rejected -> active

2. Personal PasarGuard
   draft -> awaiting_payment -> pending_review -> approved/rejected -> active

Security:
- PasarGuard API tokens are encrypted before persistence.
- Bot tokens are encrypted before persistence.
- Credentials are never returned by these services.
- Sensitive values are never intentionally logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    ApprovalRequest,
    BotInstance,
    Payment,
    SystemSetting,
    Tenant,
    TenantBranding,
    TenantCredential,
    TenantSettings,
    User,
)
from app.security.crypto import box


class ActivationPath(StrEnum):
    PRIMEVPN_REPRESENTATIVE = "primevpn_representative"
    PERSONAL_PASARGUARD = "personal_pasarguard"


class ActivationStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"


@dataclass(frozen=True)
class TenantRegistration:
    telegram_id: int
    username: str | None
    first_name: str | None

    pasarguard_login_url: str
    pasarguard_api_token: str
    pasarguard_username: str

    submitted_telegram_id: int

    bot_token: str
    brand_name: str

    slug: str

    contact_info: str | None = None
    description: str | None = None


SENSITIVE_CREDENTIAL_KINDS = frozenset(
    {
        "pasarguard_api_token",
        "pasarguard_login_url",
        "pasarguard_username",
        "owner_telegram_id",
        "bot_token",
    }
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_slug(value: str) -> str:
    value = (value or "").strip().lower()

    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    value = "".join(ch if ch in allowed else "-" for ch in value)

    while "--" in value:
        value = value.replace("--", "-")

    value = value.strip("-_")

    if not value:
        raise ValueError("slug is required")

    if len(value) > 64:
        value = value[:64].rstrip("-_")

    return value


def validate_url(value: str) -> str:
    """
    Validate a PasarGuard login URL without making any network request.

    Actual PasarGuard API verification belongs to the PasarGuard Connector
    layer in a later architecture stage.
    """

    value = (value or "").strip()

    if not value:
        raise ValueError("PasarGuard login URL is required")

    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("PasarGuard login URL must use http or https")

    if not parsed.netloc:
        raise ValueError("PasarGuard login URL is invalid")

    return value.rstrip("/")


def validate_bot_token(value: str) -> str:
    """
    Basic Telegram bot-token validation.

    This does not call Telegram and does not expose the token.
    """

    value = (value or "").strip()

    if not value:
        raise ValueError("Bot Token is required")

    # Telegram bot tokens normally contain a numeric bot id,
    # followed by a colon and a long secret string.
    if ":" not in value:
        raise ValueError("Invalid Telegram Bot Token format")

    bot_id, secret = value.split(":", 1)

    if not bot_id.isdigit() or len(bot_id) < 5:
        raise ValueError("Invalid Telegram Bot Token format")

    if len(secret) < 20:
        raise ValueError("Invalid Telegram Bot Token format")

    return value


def validate_registration(data: TenantRegistration) -> TenantRegistration:
    if not isinstance(data.telegram_id, int) or data.telegram_id <= 0:
        raise ValueError("Invalid Telegram ID")

    if not isinstance(data.submitted_telegram_id, int) or data.submitted_telegram_id <= 0:
        raise ValueError("Invalid submitted Telegram ID")

    if data.telegram_id != data.submitted_telegram_id:
        raise ValueError("Telegram Numeric ID must match the requesting Telegram account")

    if not (data.brand_name or "").strip():
        raise ValueError("Brand name is required")

    if len(data.brand_name.strip()) > 120:
        raise ValueError("Brand name is too long")

    if not (data.pasarguard_username or "").strip():
        raise ValueError("PasarGuard username is required")

    if not (data.pasarguard_api_token or "").strip():
        raise ValueError("PasarGuard API Token is required")

    login_url = validate_url(data.pasarguard_login_url)
    bot_token = validate_bot_token(data.bot_token)

    return TenantRegistration(
        telegram_id=data.telegram_id,
        username=data.username,
        first_name=data.first_name,
        pasarguard_login_url=login_url,
        pasarguard_api_token=data.pasarguard_api_token.strip(),
        pasarguard_username=data.pasarguard_username.strip(),
        submitted_telegram_id=data.submitted_telegram_id,
        bot_token=bot_token,
        brand_name=data.brand_name.strip(),
        slug=normalize_slug(data.slug),
        contact_info=(data.contact_info.strip() if data.contact_info else None),
        description=(data.description.strip() if data.description else None),
    )


async def get_or_create_user(
    db: AsyncSession,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        db.add(user)
        await db.flush()
        return user

    # Keep Telegram profile information current.
    user.username = username
    user.first_name = first_name

    await db.flush()

    return user


async def slug_exists(
    db: AsyncSession,
    slug: str,
) -> bool:
    result = await db.execute(
        select(Tenant.id).where(
            Tenant.slug == slug,
            Tenant.is_deleted.is_(False),
        )
    )

    return result.scalar_one_or_none() is not None


async def unique_slug(
    db: AsyncSession,
    requested_slug: str,
) -> str:
    base = normalize_slug(requested_slug)

    if not await slug_exists(db, base):
        return base

    for index in range(2, 10000):
        candidate = f"{base}-{index}"

        if len(candidate) > 64:
            candidate = candidate[:64].rstrip("-_")

        if not await slug_exists(db, candidate):
            return candidate

    raise RuntimeError("Unable to generate a unique tenant slug")


def encrypt_sensitive(value: str) -> tuple[str, str]:
    """
    Store encrypted + masked representation only.

    The plaintext value is never returned.
    """

    encrypted = box.encrypt(value)
    masked = box.mask(value)

    return encrypted, masked


async def store_credential(
    db: AsyncSession,
    tenant_id: int,
    kind: str,
    value: str,
) -> TenantCredential:
    encrypted, masked = encrypt_sensitive(value)

    credential = TenantCredential(
        tenant_id=tenant_id,
        kind=kind,
        encrypted_value=encrypted,
        masked_value=masked,
        created_at=utcnow(),
    )

    db.add(credential)
    await db.flush()

    return credential


async def get_activation_fee(
    db: AsyncSession,
) -> int:
    """
    Prefer SystemSetting when configured.

    The fallback remains 250,000 تومان, as specified by Page 3.
    """

    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "activation_fee_toman")
    )

    setting = result.scalar_one_or_none()

    if setting is None:
        return 250_000

    try:
        amount = int(setting.value)
    except (TypeError, ValueError):
        return 250_000

    if amount < 0:
        return 250_000

    return amount


async def create_draft_tenant(
    db: AsyncSession,
    registration: TenantRegistration,
    path: ActivationPath,
) -> tuple[Tenant, User]:
    """
    Create the tenant and all protected credentials.

    The initial tenant is always created as draft.
    The caller moves it to the correct next state only after all
    records are successfully prepared.
    """

    registration = validate_registration(registration)

    user = await get_or_create_user(
        db,
        telegram_id=registration.telegram_id,
        username=registration.username,
        first_name=registration.first_name,
    )

    slug = await unique_slug(db, registration.slug)

    tenant = Tenant(
        slug=slug,
        name=registration.brand_name,
        status=ActivationStatus.DRAFT.value,
        is_deleted=False,
        created_at=utcnow(),
    )

    db.add(tenant)
    await db.flush()

    settings = TenantSettings(
        tenant_id=tenant.id,
        settings={
            "activation_path": path.value,
            "contact_info": registration.contact_info,
            "description": registration.description,
            "owner_telegram_id": registration.telegram_id,
        },
    )

    branding = TenantBranding(
        tenant_id=tenant.id,
        display_name=registration.brand_name,
    )

    db.add(settings)
    db.add(branding)

    # Sensitive credentials are encrypted individually.
    await store_credential(
        db,
        tenant.id,
        "pasarguard_api_token",
        registration.pasarguard_api_token,
    )

    await store_credential(
        db,
        tenant.id,
        "pasarguard_login_url",
        registration.pasarguard_login_url,
    )

    await store_credential(
        db,
        tenant.id,
        "pasarguard_username",
        registration.pasarguard_username,
    )

    await store_credential(
        db,
        tenant.id,
        "owner_telegram_id",
        str(registration.submitted_telegram_id),
    )

    await store_credential(
        db,
        tenant.id,
        "bot_token",
        registration.bot_token,
    )

    bot_encrypted, bot_masked = encrypt_sensitive(registration.bot_token)

    bot = BotInstance(
        tenant_id=tenant.id,
        name=registration.brand_name,
        encrypted_token=bot_encrypted,
        masked_token=bot_masked,
        status="pending",
        error_count=0,
    )

    db.add(bot)

    await db.flush()

    return tenant, user


async def create_approval_request(
    db: AsyncSession,
    tenant_id: int,
    path: ActivationPath,
    user_id: int,
) -> ApprovalRequest:
    """
    Create an owner-review request.

    The applicant is linked through tenant settings / tenant-user
    relationships in the current schema. The request itself never stores
    sensitive credentials.
    """

    request = ApprovalRequest(
        tenant_id=tenant_id,
        path=path.value,
        status=ActivationStatus.PENDING_REVIEW.value,
        reviewer_id=None,
        note=None,
        created_at=utcnow(),
    )

    db.add(request)
    await db.flush()

    return request


async def create_personal_activation_payment(
    db: AsyncSession,
    tenant_id: int,
    user_id: int,
) -> Payment:
    """
    Create the real payment record for the personal-panel activation fee.

    This is a payment intent/record, NOT a fake successful payment.

    It remains pending until a real payment provider or the approved
    manual-payment workflow confirms it.
    """

    fee = await get_activation_fee(db)

    payment = Payment(
        tenant_id=tenant_id,
        order_id=None,
        provider="activation",
        status="pending",
        amount=fee,
        reference=None,
        idempotency_key=f"tenant-activation:{tenant_id}:{user_id}",
    )

    db.add(payment)
    await db.flush()

    return payment


async def submit_registration(
    db: AsyncSession,
    registration: TenantRegistration,
    path: ActivationPath,
) -> dict[str, Any]:
    """
    Main registration entry point.

    PRIMEVPN representative:
        draft -> pending_review

    Personal PasarGuard:
        draft -> awaiting_payment
        payment must later be confirmed
        awaiting_payment -> pending_review
    """

    registration = validate_registration(registration)

    tenant, user = await create_draft_tenant(
        db=db,
        registration=registration,
        path=path,
    )

    payment = None

    if path == ActivationPath.PRIMEVPN_REPRESENTATIVE:
        tenant.status = ActivationStatus.PENDING_REVIEW.value

        approval = await create_approval_request(
            db=db,
            tenant_id=tenant.id,
            path=path,
            user_id=user.id,
        )

    elif path == ActivationPath.PERSONAL_PASARGUARD:
        tenant.status = ActivationStatus.AWAITING_PAYMENT.value

        payment = await create_personal_activation_payment(
            db=db,
            tenant_id=tenant.id,
            user_id=user.id,
        )

        approval = None

    else:
        raise ValueError(f"Unsupported activation path: {path}")

    await db.flush()

    return {
        "tenant_id": tenant.id,
        "user_id": user.id,
        "status": tenant.status,
        "path": path.value,
        "approval_id": approval.id if approval else None,
        "payment_id": payment.id if payment else None,
        "activation_fee_toman": payment.amount if payment else 0,
    }


async def confirm_personal_activation_payment(
    db: AsyncSession,
    tenant_id: int,
    payment_id: int,
    reference: str | None = None,
) -> ApprovalRequest:
    """
    Move a paid personal activation request to owner review.

    This function must only be called after the payment has been
    legitimately verified by the payment layer.

    It intentionally does not claim payment success by itself.
    """

    payment_result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
        )
    )

    payment = payment_result.scalar_one_or_none()

    if payment is None:
        raise ValueError("Activation payment not found")

    if payment.status != "paid":
        raise ValueError("Activation payment must be verified before owner review")

    if reference:
        payment.reference = reference

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))

    tenant = tenant_result.scalar_one_or_none()

    if tenant is None or tenant.is_deleted:
        raise ValueError("Tenant not found")

    if tenant.status != ActivationStatus.AWAITING_PAYMENT.value:
        raise ValueError(f"Invalid tenant state: {tenant.status}")

    tenant.status = ActivationStatus.PENDING_REVIEW.value

    # Find the requesting user through the tenant settings owner id.
    settings_result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )

    settings = settings_result.scalar_one_or_none()

    if settings is None:
        raise ValueError("Tenant settings not found")

    owner_telegram_id = settings.settings.get("owner_telegram_id")

    if not owner_telegram_id:
        raise ValueError("Applicant Telegram ID not found")

    user_result = await db.execute(select(User).where(User.telegram_id == int(owner_telegram_id)))

    user = user_result.scalar_one_or_none()

    if user is None:
        raise ValueError("Applicant user not found")

    approval = await create_approval_request(
        db=db,
        tenant_id=tenant_id,
        path=ActivationPath.PERSONAL_PASARGUARD,
        user_id=user.id,
    )

    await db.flush()

    return approval


async def approve_tenant(
    db: AsyncSession,
    approval_id: int,
) -> Tenant:
    """
    Owner approval.

    pending_review -> approved

    Activation itself is intentionally a separate state transition so
    the bot runtime cannot accidentally start before the activation
    operation is complete.
    """

    result = await db.execute(
        select(ApprovalRequest, Tenant)
        .join(
            Tenant,
            Tenant.id == ApprovalRequest.tenant_id,
        )
        .where(ApprovalRequest.id == approval_id)
    )

    row = result.first()

    if row is None:
        raise ValueError("Approval request not found")

    approval, tenant = row

    if approval.status != ActivationStatus.PENDING_REVIEW.value:
        raise ValueError(f"Approval request is not pending: {approval.status}")

    if tenant.status != ActivationStatus.PENDING_REVIEW.value:
        raise ValueError(f"Tenant is not pending review: {tenant.status}")

    approval.status = ActivationStatus.APPROVED.value
    tenant.status = ActivationStatus.APPROVED.value

    await db.flush()

    return tenant


async def reject_tenant(
    db: AsyncSession,
    approval_id: int,
    note: str | None = None,
) -> Tenant:
    """
    Owner rejection.

    pending_review -> rejected
    """

    result = await db.execute(
        select(ApprovalRequest, Tenant)
        .join(
            Tenant,
            Tenant.id == ApprovalRequest.tenant_id,
        )
        .where(ApprovalRequest.id == approval_id)
    )

    row = result.first()

    if row is None:
        raise ValueError("Approval request not found")

    approval, tenant = row

    if approval.status != ActivationStatus.PENDING_REVIEW.value:
        raise ValueError(f"Approval request is not pending: {approval.status}")

    approval.status = ActivationStatus.REJECTED.value
    approval.note = note[:1000] if note else None

    tenant.status = ActivationStatus.REJECTED.value

    await db.flush()

    return tenant


async def activate_approved_tenant(
    db: AsyncSession,
    tenant_id: int,
) -> Tenant:
    """
    Final state transition:

        approved -> active

    Runtime startup should happen after this transition and belongs to
    the Tenant Bot Runtime layer.
    """

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))

    tenant = result.scalar_one_or_none()

    if tenant is None or tenant.is_deleted:
        raise ValueError("Tenant not found")

    if tenant.status != ActivationStatus.APPROVED.value:
        raise ValueError(f"Tenant cannot be activated from state: {tenant.status}")

    tenant.status = ActivationStatus.ACTIVE.value

    result = await db.execute(select(BotInstance).where(BotInstance.tenant_id == tenant_id))

    bot = result.scalar_one_or_none()

    if bot is not None:
        bot.status = "active"

    await db.flush()

    return tenant


async def get_latest_activation(
    db: AsyncSession,
    telegram_id: int,
) -> dict[str, Any] | None:
    """
    Return the latest activation request for a Telegram user.

    Sensitive credentials are never selected or returned.
    """

    user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))

    user = user_result.scalar_one_or_none()

    if user is None:
        return None

    settings_result = await db.execute(
        select(TenantSettings)
        .where(TenantSettings.settings["owner_telegram_id"].as_string() == str(telegram_id))
        .order_by(TenantSettings.tenant_id.desc())
    )

    settings = settings_result.scalars().first()

    if settings is None:
        return None

    result = await db.execute(select(Tenant).where(Tenant.id == settings.tenant_id))

    tenant = result.scalar_one_or_none()

    if tenant is None:
        return None

    approval_result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.tenant_id == tenant.id)
        .order_by(ApprovalRequest.created_at.desc())
    )

    approval = approval_result.scalars().first()

    return {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "tenant_slug": tenant.slug,
        "tenant_status": tenant.status,
        "approval_id": approval.id if approval else None,
        "approval_status": approval.status if approval else None,
        "approval_path": approval.path if approval else None,
    }
