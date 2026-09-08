"""
3XSHOP Platform Core

Page 1 - Platform definition

3XSHOP is an independent multi-tenant platform.
PasarGuard is NEVER the runtime core of this platform.

The platform supports two onboarding paths:

1. PRIMEVPN representative:
   The tenant connects its dedicated bot to the platform owner's
   PasarGuard installation.

2. Personal PasarGuard:
   The tenant provides its own PasarGuard connection and pays the
   one-time activation fee. Activation still requires platform-owner approval.

Important:
- Every onboarding request requires owner approval.
- PasarGuard is an external connector.
- Tenant runtime must not depend on the owner's PasarGuard being available.
"""

from __future__ import annotations

from enum import StrEnum


class OnboardingPath(StrEnum):
    """
    The two officially supported 3XSHOP activation paths.
    """

    PRIMEVPN_REPRESENTATIVE = "primevpn_representative"
    PERSONAL_PASARGUARD = "personal_pasarguard"


class TenantLifecycle(StrEnum):
    """
    High-level tenant lifecycle.

    The detailed approval/payment state machine is implemented in the
    onboarding/approval modules. These values describe the platform-level
    lifecycle only.
    """

    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class ApprovalStatus(StrEnum):
    """
    Owner approval is mandatory for every onboarding request.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PlatformContract:
    """
    Immutable platform-level rules derived from GitBook page 1.

    Keeping these rules in one place prevents later modules from
    accidentally turning PasarGuard into a core dependency.
    """

    NAME = "3XSHOP"

    # PasarGuard is an external integration, not the platform runtime.
    PASARGUARD_IS_EXTERNAL_CONNECTOR = True

    # Every tenant activation requires owner approval.
    OWNER_APPROVAL_REQUIRED = True

    # The personal PasarGuard route has a one-time activation fee.
    PERSONAL_ACTIVATION_FEE_TOMAN = 250_000

    @classmethod
    def validate_onboarding_path(cls, path: str | OnboardingPath) -> OnboardingPath:
        """
        Normalize and validate an onboarding path.
        """

        try:
            return OnboardingPath(path)
        except ValueError as exc:
            raise ValueError(f"Unsupported 3XSHOP onboarding path: {path!r}") from exc

    @classmethod
    def requires_owner_approval(cls, path: str | OnboardingPath) -> bool:
        """
        Both supported onboarding paths require platform-owner approval.
        """

        cls.validate_onboarding_path(path)
        return cls.OWNER_APPROVAL_REQUIRED

    @classmethod
    def requires_activation_payment(
        cls,
        path: str | OnboardingPath,
    ) -> bool:
        """
        Only the personal PasarGuard route requires the one-time activation fee.
        """

        normalized = cls.validate_onboarding_path(path)
        return normalized == OnboardingPath.PERSONAL_PASARGUARD

    @classmethod
    def activation_fee_toman(
        cls,
        path: str | OnboardingPath,
    ) -> int:
        """
        Return the activation fee required by the platform contract.
        """

        if cls.requires_activation_payment(path):
            return cls.PERSONAL_ACTIVATION_FEE_TOMAN

        return 0


def is_valid_platform_tenant_status(status: str) -> bool:
    """
    Check whether a tenant status belongs to the platform lifecycle.
    """

    try:
        TenantLifecycle(status)
        return True
    except ValueError:
        return False


def is_valid_approval_status(status: str) -> bool:
    """
    Check whether an approval status belongs to the platform contract.
    """

    try:
        ApprovalStatus(status)
        return True
    except ValueError:
        return False
