import pytest

from app.api.routers import auth


@pytest.mark.asyncio
async def test_global_claims_grants_owner_permissions(monkeypatch):
    monkeypatch.setattr(auth.settings, "owner_telegram_id", 777)

    claims = await auth._global_claims(777, 42, {"username": "owner"})

    assert claims["is_platform_owner"] is True
    assert claims["role"] == "Owner"
    assert claims["user_id"] == 42
    assert "dashboard.read" in claims["permissions"]
    assert "auth.telegram" in claims["permissions"]


@pytest.mark.asyncio
async def test_global_claims_does_not_elevate_regular_user(monkeypatch):
    monkeypatch.setattr(auth.settings, "owner_telegram_id", 777)

    claims = await auth._global_claims(778, 43, {"username": "customer"})

    assert claims["is_platform_owner"] is False
    assert claims["role"] is None
    assert claims["permissions"] == ["auth.telegram"]
