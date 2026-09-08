from __future__ import annotations

from dataclasses import dataclass

from app.security.crypto import box

from .base import PasarGuardCredentials


@dataclass(frozen=True)
class EncryptedPasarGuardCredentials:
    base_url: str
    encrypted_api_token: str
    encrypted_username: str | None = None


def encrypt_credentials(
    credentials: PasarGuardCredentials,
) -> EncryptedPasarGuardCredentials:
    encrypted_token = box.encrypt(credentials.api_token)

    encrypted_username = None
    if credentials.username:
        encrypted_username = box.encrypt(credentials.username)

    return EncryptedPasarGuardCredentials(
        base_url=credentials.base_url,
        encrypted_api_token=encrypted_token,
        encrypted_username=encrypted_username,
    )


def decrypt_credentials(
    encrypted: EncryptedPasarGuardCredentials,
) -> PasarGuardCredentials:
    token = box.decrypt(encrypted.encrypted_api_token)

    username = None
    if encrypted.encrypted_username:
        username = box.decrypt(encrypted.encrypted_username)

    return PasarGuardCredentials(
        base_url=encrypted.base_url,
        api_token=token,
        username=username,
    )


def mask_credentials(
    credentials: PasarGuardCredentials,
) -> dict[str, str | None]:
    return {
        "base_url": credentials.base_url,
        "api_token": "***REDACTED***",
        "username": credentials.username,
    }
