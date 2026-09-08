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
