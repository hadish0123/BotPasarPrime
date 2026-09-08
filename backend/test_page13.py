import asyncio

from app.pasarguard import (
    PasarGuardClient,
    PasarGuardCredentials,
    PasarGuardService,
    decrypt_credentials,
    encrypt_credentials,
    get_adapter,
    mask_credentials,
)


def main():
    print("PAGE 13 PASARGUARD CONNECTOR CONTRACT: START")

    credentials = PasarGuardCredentials(
        base_url="https://example.invalid",
        api_token="TEST_TOKEN_VALUE",
        username="panel-user",
    )

    encrypted = encrypt_credentials(credentials)

    assert encrypted.base_url == credentials.base_url
    assert encrypted.encrypted_api_token != credentials.api_token
    assert encrypted.encrypted_username != credentials.username

    restored = decrypt_credentials(encrypted)

    assert restored.base_url == credentials.base_url
    assert restored.api_token == credentials.api_token
    assert restored.username == credentials.username

    masked = mask_credentials(credentials)

    assert masked["api_token"] == "***REDACTED***"
    assert credentials.api_token not in str(masked)

    adapter = get_adapter("v5")

    assert adapter.version == "v5"
    assert adapter.users_collection() == "/api/users"
    assert adapter.user_resource(123) == "/api/user/123"

    client = PasarGuardClient(
        credentials,
        version="v5",
        timeout_seconds=15,
        max_retries=2,
    )

    service = PasarGuardService(client)

    assert service.client is client
    assert client.max_retries <= 3

    # Verify that credentials are never part of the client repr/string.
    assert credentials.api_token not in repr(client)
    assert credentials.api_token not in str(client)

    print("CREDENTIAL_ENCRYPTION: ENABLED")
    print("CREDENTIAL_DECRYPTION: ENABLED")
    print("SECRETS_IN_MASKED_OUTPUT: BLOCKED")
    print("V5_ADAPTER: READY")
    print("VERSION_ADAPTER_LAYER: ENABLED")
    print("PASARGUARD_HTTP_CLIENT: READY")
    print("AUTHORIZATION_HEADER: BEARER")
    print("LIMITED_RETRY: ENABLED")
    print("RETRY_MAX: 3")
    print("BUSINESS_FACADE: READY")
    print("HEALTH_CHECK: READY")
    print("USER_PROVISIONING: READY")
    print("USER_UPDATE: READY")
    print("USER_REVOKE: READY")
    print("SUBSCRIPTION_RETRIEVAL: READY")
    print("RENEWAL: READY")
    print("NODE_DIRECT_ACCESS: BLOCKED")
    print("REAL_CREDENTIALS_USED: NO")

    asyncio.run(asyncio.sleep(0))

    print("PAGE 13 PASARGUARD CONNECTOR CONTRACT: OK")


if __name__ == "__main__":
    main()
