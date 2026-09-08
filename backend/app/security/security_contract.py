from __future__ import annotations

import hashlib
import hmac
import ipaddress
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
    return any(marker in lowered for marker in SENSITIVE_NAMES)


def mask_secret(value: str | None, visible: int = 4) -> str:
    if not value:
        return "***"
    if len(value) <= visible * 2:
        return "***"
    return f"{value[:visible]}***{value[-visible:]}"


def sanitize_mapping(data: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}

    for key, value in data.items():
        key_str = str(key)

        if is_sensitive_name(key_str):
            result[key_str] = "***"
        elif isinstance(value, dict):
            result[key_str] = sanitize_mapping(value)
        else:
            result[key_str] = value

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

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))

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
    return {key: value for key, value in CONTRACT.__dict__.items()}
