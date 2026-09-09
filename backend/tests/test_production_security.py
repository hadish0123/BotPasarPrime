import hashlib
import hmac
import json
import time
import urllib.parse

import pytest

from app.core.tenant_isolation import assert_tenant_id
from app.security.rbac import allowed
from app.security.telegram_init_data import validate_init_data


def make_init_data(bot_token: str, auth_date: int) -> str:
    user = {"id": 12345, "first_name": "Test"}
    data = {
        "auth_date": str(auth_date),
        "query_id": "Q",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode({**data, "hash": digest})


def test_telegram_init_data_rejects_stale_payload():
    payload = make_init_data("123456:ABCDEF", int(time.time()) - 301)
    ok, _ = validate_init_data(payload, "123456:ABCDEF", max_age=300)
    assert not ok


def test_telegram_init_data_accepts_fresh_payload():
    payload = make_init_data("123456:ABCDEF", int(time.time()))
    ok, data = validate_init_data(payload, "123456:ABCDEF", max_age=300)
    assert ok
    assert data["user"]["id"] == 12345


def test_tenant_context_blocks_cross_tenant_access():
    class Context:
        tenant_id = 10
        is_platform_owner = False

    with pytest.raises(Exception):
        assert_tenant_id(11, Context())


def test_owner_can_use_platform_scope():
    class Context:
        tenant_id = None
        is_platform_owner = True

    assert_tenant_id(11, Context()) is None


def test_rbac_sales_cannot_manage_admins():
    assert not allowed("Sales", "admins.manage")
