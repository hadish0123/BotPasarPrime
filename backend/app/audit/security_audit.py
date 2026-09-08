from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

SENSITIVE_ACTIONS = {
    "login",
    "logout",
    "tenant_create",
    "tenant_approve",
    "tenant_reject",
    "tenant_activate",
    "tenant_suspend",
    "credential_create",
    "credential_update",
    "credential_delete",
    "payment_verify",
    "payment_reject",
    "wallet_credit",
    "wallet_debit",
    "order_create",
    "order_cancel",
    "admin_role_change",
    "settings_change",
    "backup_create",
    "backup_restore",
}


@dataclass(frozen=True)
class AuditEvent:
    action: str
    actor_id: int | None
    tenant_id: int | None
    target_id: int | None
    ip_address: str | None
    success: bool
    created_at: datetime

    @classmethod
    def create(
        cls,
        action: str,
        actor_id: int | None = None,
        tenant_id: int | None = None,
        target_id: int | None = None,
        ip_address: str | None = None,
        success: bool = True,
    ) -> AuditEvent:
        if action not in SENSITIVE_ACTIONS:
            raise ValueError("Unsupported audit action")

        return cls(
            action=action,
            actor_id=actor_id,
            tenant_id=tenant_id,
            target_id=target_id,
            ip_address=ip_address,
            success=success,
            created_at=datetime.now(UTC),
        )


def is_sensitive_action(action: str) -> bool:
    return action in SENSITIVE_ACTIONS
