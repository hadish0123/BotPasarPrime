from __future__ import annotations

import pytest

from app.pasarguard.adapters import get_adapter
from app.pasarguard.base import (
    PasarGuardCredentials,
    PasarGuardUnsupportedVersion,
)
from app.pasarguard.credentials import decrypt_credentials, encrypt_credentials, mask_credentials


def test_adapter_version_and_paths() -> None:
    adapter = get_adapter("V5")
    assert adapter.version == "v5"
    assert adapter.users_collection() == "/api/users"
    assert adapter.user_resource("alice") == "/api/user/alice"
    assert adapter.user_subscription("alice") == "/api/user/alice"


def test_unsupported_adapter_is_rejected() -> None:
    with pytest.raises(PasarGuardUnsupportedVersion):
        get_adapter("v99")


def test_credentials_are_validated_and_masked() -> None:
    credentials = PasarGuardCredentials(
        base_url="https://panel.example/",
        api_token=" secret-token ",
        username=" admin ",
    )
    assert credentials.base_url == "https://panel.example"
    assert credentials.api_token == "secret-token"
    assert credentials.username == "admin"
    assert mask_credentials(credentials)["api_token"] == "***REDACTED***"


def test_credentials_encrypt_and_round_trip() -> None:
    credentials = PasarGuardCredentials(
        base_url="https://panel.example",
        api_token="secret-token",
        username="admin",
    )
    encrypted = encrypt_credentials(credentials)
    assert encrypted.encrypted_api_token != credentials.api_token
    restored = decrypt_credentials(encrypted)
    assert restored == credentials
