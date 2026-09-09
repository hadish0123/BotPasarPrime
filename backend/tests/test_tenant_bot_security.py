import pytest

from app.api.routers.services import _admin
from app.bot.tenant import TenantBotContract, TenantIsolationViolation, assert_tenant_access
from app.services.provisioning import MAX_PROVISION_RETRIES


def test_tenant_bot_contract_blocks_cross_tenant_access():
    contract = TenantBotContract(tenant_id=7, bot_instance_id=11)
    assert_tenant_access(contract, 7)
    with pytest.raises(TenantIsolationViolation):
        assert_tenant_access(contract, 8)


def test_tenant_wide_service_access_requires_write_permission():
    assert _admin({"is_platform_owner": True})
    assert _admin({"permissions": ["services.write"]})
    assert not _admin({"permissions": ["services.read"]})
    assert not _admin({"permissions": ["orders.read", "services.read"]})


def test_provisioning_retry_policy_is_bounded():
    assert MAX_PROVISION_RETRIES == 3
    assert 1 < MAX_PROVISION_RETRIES < 10
