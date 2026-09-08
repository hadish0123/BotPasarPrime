from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.entities import AuditLog

SENSITIVE_KEYS = {
    "token",
    "api_token",
    "bot_token",
    "password",
    "passwd",
    "secret",
    "secret_key",
    "api_key",
    "authorization",
    "cookie",
    "set_cookie",
    "encrypted_value",
    "credential",
    "credentials",
    "access_token",
    "refresh_token",
}


SENSITIVE_ACTIONS = {
    "tenant.create",
    "tenant.update",
    "tenant.suspend",
    "tenant.deactivate",
    "tenant.activate",
    "credential.change",
    "payment.verify",
    "payment.reject",
    "payment.refund",
    "wallet.credit",
    "wallet.debit",
    "role.change",
    "product.change",
    "price.change",
    "service.create",
    "service.update",
    "service.revoke",
}


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}

        for key, item in value.items():
            normalized = str(key).strip().lower()

            if normalized in SENSITIVE_KEYS:
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = sanitize_metadata(item)

        return result

    if isinstance(value, (list, tuple, set)):
        return [sanitize_metadata(item) for item in value]

    return value


def audit(
    db,
    action: str,
    tenant_id=None,
    actor_type: str = "system",
    actor_id=None,
    target_type=None,
    target_id=None,
    metadata=None,
):
    safe_metadata = sanitize_metadata(metadata or {})

    entry = AuditLog(
        tenant_id=tenant_id,
        actor_type=str(actor_type),
        actor_id=str(actor_id) if actor_id is not None else None,
        action=str(action),
        target_type=str(target_type) if target_type is not None else None,
        target_id=str(target_id) if target_id is not None else None,
        metadata_json=safe_metadata,
    )

    db.add(entry)
    return entry


def is_sensitive_action(action: str) -> bool:
    return action in SENSITIVE_ACTIONS


def audit_sensitive(
    db,
    *,
    action: str,
    tenant_id,
    actor_type: str,
    actor_id,
    target_type: str,
    target_id,
    metadata=None,
):
    if not is_sensitive_action(action):
        raise ValueError(f"Unsupported sensitive audit action: {action}")

    return audit(
        db=db,
        action=action,
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )
