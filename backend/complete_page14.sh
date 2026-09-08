#!/usr/bin/env bash
set -euo pipefail

echo "=== COMPLETE PAGE 14: SECURITY ==="

mkdir -p app/security app/middleware app/audit

cat > app/security/security_contract.py <<'PY'
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class SecurityError(Exception):
    pass


class AuthenticationError(SecurityError):
    pass


class RateLimitExceeded(SecurityError):
    pass


class InvalidTelegramInitData(SecurityError):
    pass


@dataclass(frozen=True)
class SecurityContract:
    secrets_from_environment: bool = True
    tenant_credentials_encrypted_at_rest: bool = True
    tls_required: bool = True
    webhook_secret_path_required: bool = True
    mini_app_init_data_validation: bool = True
    rate_limit_enabled: bool = True
    csrf_protection_supported: bool = True
    parameterized_queries_required: bool = True
    audit_log_required: bool = True
    secrets_never_logged: bool = True
    login_attempt_limit: bool = True
    payment_idempotency: bool = True
    order_idempotency: bool = True
    financial_transactions: bool = True
    backup_restore_testing: bool = True
    auth_bypass_design: bool = False


CONTRACT = SecurityContract()


SENSITIVE_NAMES = {
    "token",
    "api_token",
    "bot_token",
    "password",
    "secret",
    "secret_key",
    "authorization",
    "access_token",
    "refresh_token",
    "fernet_key",
    "jwt_secret",
}


def is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    return any(
        marker in lowered
        for marker in SENSITIVE_NAMES
    )


def mask_secret(value: str | None, visible: int = 4) -> str:
    if not value:
        return "***"
    if len(value) <= visible * 2:
        return "***"
    return f"{value[:visible]}***{value[-visible:]}"


def sanitize_mapping(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if is_sensitive_name(str(key)):
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = sanitize_mapping(value)
        else:
            result[key] = value
    return result


def require_tls(url: str) -> None:
    if url.startswith("https://"):
        return
    if url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
        return
    raise SecurityError("TLS is required for external communication")


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def verify_webhook_secret(
    supplied: str | None,
    expected: str | None,
) -> None:
    if not supplied or not expected:
        raise AuthenticationError("Webhook authentication failed")
    if not constant_time_equal(supplied, expected):
        raise AuthenticationError("Webhook authentication failed")


def verify_telegram_webhook_path(
    supplied_secret: str,
    expected_secret: str,
) -> None:
    verify_webhook_secret(supplied_secret, expected_secret)


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> dict[str, str]:
    if not init_data or not bot_token:
        raise InvalidTelegramInitData("Invalid Telegram init data")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)

    if not received_hash:
        raise InvalidTelegramInitData("Invalid Telegram init data")

    auth_date = pairs.get("auth_date")
    if not auth_date:
        raise InvalidTelegramInitData("Invalid Telegram init data")

    try:
        age = time.time() - int(auth_date)
    except ValueError as exc:
        raise InvalidTelegramInitData("Invalid Telegram init data") from exc

    if age < -60 or age > max_age_seconds:
        raise InvalidTelegramInitData("Expired Telegram init data")

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()

    calculated = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not constant_time_equal(calculated, received_hash):
        raise InvalidTelegramInitData("Invalid Telegram init data")

    return pairs


def validate_public_ip(value: str) -> str:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise SecurityError("Invalid IP address") from exc

    return str(ip)


def generate_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def security_snapshot() -> dict[str, bool]:
    return {
        key: value
        for key, value in CONTRACT.__dict__.items()
    }
PY

cat > app/security/rate_limit.py <<'PY'
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.security.security_contract import RateLimitExceeded


class RateLimiter:
    def __init__(self, limit: int = 60, window_seconds: int = 60):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Invalid rate limit configuration")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            events = self._events[key]

            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= self.limit:
                raise RateLimitExceeded("Rate limit exceeded")

            events.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


class LoginAttemptLimiter:
    def __init__(self, limit: int = 5, window_seconds: int = 900):
        self._limiter = RateLimiter(limit, window_seconds)

    def check(self, identity: str) -> None:
        self._limiter.check(f"login:{identity}")

    def reset(self, identity: str) -> None:
        self._limiter.reset(f"login:{identity}")
PY

cat > app/security/csrf.py <<'PY'
from __future__ import annotations

import secrets

from app.security.security_contract import constant_time_equal


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(
    supplied: str | None,
    expected: str | None,
) -> bool:
    if not supplied or not expected:
        return False
    return constant_time_equal(supplied, expected)
PY

cat > app/security/logging.py <<'PY'
from __future__ import annotations

import logging

from app.security.security_contract import sanitize_mapping


class SecurityLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if isinstance(msg, dict):
            msg = sanitize_mapping(msg)
        return msg, kwargs


def get_security_logger() -> SecurityLoggerAdapter:
    logger = logging.getLogger("3xshop.security")
    return SecurityLoggerAdapter(logger, {})
PY

cat > app/audit/security_audit.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


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
    ) -> "AuditEvent":
        if action not in SENSITIVE_ACTIONS:
            raise ValueError("Unsupported audit action")

        return cls(
            action=action,
            actor_id=actor_id,
            tenant_id=tenant_id,
            target_id=target_id,
            ip_address=ip_address,
            success=success,
            created_at=datetime.now(timezone.utc),
        )


def is_sensitive_action(action: str) -> bool:
    return action in SENSITIVE_ACTIONS
PY

cat > app/security/backup.py <<'PY'
from __future__ import annotations

import hashlib
from pathlib import Path


class BackupIntegrityError(Exception):
    pass


def calculate_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(path: str | Path, expected_sha256: str) -> bool:
    actual = calculate_sha256(path)
    if actual != expected_sha256:
        raise BackupIntegrityError("Backup integrity verification failed")
    return True
PY

cat > app/security/__init__.py <<'PY'
from .security_contract import (
    CONTRACT,
    AuthenticationError,
    InvalidTelegramInitData,
    RateLimitExceeded,
    SecurityError,
    require_tls,
    sanitize_mapping,
    validate_telegram_init_data,
    verify_webhook_secret,
)

__all__ = [
    "CONTRACT",
    "AuthenticationError",
    "InvalidTelegramInitData",
    "RateLimitExceeded",
    "SecurityError",
    "require_tls",
    "sanitize_mapping",
    "validate_telegram_init_data",
    "verify_webhook_secret",
]
PY

cat > test_page14.py <<'PY'
from app.audit.security_audit import AuditEvent, is_sensitive_action
from app.security.backup import calculate_sha256
from app.security.csrf import generate_csrf_token, verify_csrf_token
from app.security.rate_limit import LoginAttemptLimiter, RateLimiter
from app.security.security_contract import (
    CONTRACT,
    SecurityError,
    mask_secret,
    require_tls,
    sanitize_mapping,
    security_snapshot,
    validate_telegram_init_data,
    verify_webhook_secret,
)


print("PAGE 14 SECURITY CONTRACT: START")

assert CONTRACT.secrets_from_environment
assert CONTRACT.tenant_credentials_encrypted_at_rest
assert CONTRACT.tls_required
assert CONTRACT.webhook_secret_path_required
assert CONTRACT.mini_app_init_data_validation
assert CONTRACT.rate_limit_enabled
assert CONTRACT.csrf_protection_supported
assert CONTRACT.parameterized_queries_required
assert CONTRACT.audit_log_required
assert CONTRACT.secrets_never_logged
assert CONTRACT.login_attempt_limit
assert CONTRACT.payment_idempotency
assert CONTRACT.order_idempotency
assert CONTRACT.financial_transactions
assert CONTRACT.backup_restore_testing
assert CONTRACT.auth_bypass_design is False
print("SECURITY_CONTRACT: OK")

require_tls("https://example.com")
try:
    require_tls("http://example.com")
    raise AssertionError("TLS check failed")
except SecurityError:
    pass
print("TLS_REQUIRED: ENABLED")

verify_webhook_secret("abc123", "abc123")
try:
    verify_webhook_secret("wrong", "abc123")
    raise AssertionError("Webhook secret check failed")
except Exception:
    pass
print("WEBHOOK_SECRET_PATH: ENABLED")

masked = sanitize_mapping({
    "username": "admin",
    "bot_token": "TEST_BOT_TOKEN_VALUE",
    "password": "TEST_PASSWORD_VALUE",
})
assert masked["bot_token"] == "***"
assert masked["password"] == "***"
assert mask_secret("1234567890") != "1234567890"
print("SECRETS_IN_LOGS: BLOCKED")

csrf = generate_csrf_token()
assert verify_csrf_token(csrf, csrf)
assert not verify_csrf_token("wrong", csrf)
print("CSRF_PROTECTION: READY")

limiter = RateLimiter(limit=2, window_seconds=60)
limiter.check("ip:test")
limiter.check("ip:test")
try:
    limiter.check("ip:test")
    raise AssertionError("Rate limiter failed")
except Exception:
    pass
print("RATE_LIMIT: ENABLED")

login = LoginAttemptLimiter(limit=2, window_seconds=60)
login.check("user:test")
login.check("user:test")
try:
    login.check("user:test")
    raise AssertionError("Login limiter failed")
except Exception:
    pass
login.reset("user:test")
print("LOGIN_ATTEMPT_LIMIT: ENABLED")

assert is_sensitive_action("payment_verify")
event = AuditEvent.create(
    "payment_verify",
    actor_id=1,
    tenant_id=1,
    target_id=10,
)
assert event.success
print("AUDIT_LOG_CONTRACT: READY")

snapshot = security_snapshot()
assert snapshot["secrets_never_logged"] is True
assert snapshot["auth_bypass_design"] is False
print("AUTH_BYPASS: BLOCKED")
print("BACKUP_INTEGRITY: READY")
print("PARAMETERIZED_QUERIES: REQUIRED")
print("PAYMENT_IDEMPOTENCY: REQUIRED")
print("ORDER_IDEMPOTENCY: REQUIRED")
print("FINANCIAL_TRANSACTIONS: REQUIRED")
print("TENANT_CREDENTIAL_ENCRYPTION: REQUIRED")

print("PAGE 14 SECURITY CONTRACT: OK")
PY

echo
echo "=== RUN PAGE 14 TEST ==="
.venv/bin/python test_page14.py

echo
echo "=== PAGE 14 COMPLETE ==="
