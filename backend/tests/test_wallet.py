from decimal import Decimal

import pytest

from app.services.wallet import post_wallet_transaction


class W:
    balance = Decimal("100")


class S:
    def __init__(self):
        self.x = set()


@pytest.mark.asyncio
async def test_debit_api_contract():
    import inspect

    assert inspect.iscoroutinefunction(post_wallet_transaction)
    assert "idempotency_key" in inspect.signature(post_wallet_transaction).parameters
