import pytest

from app.bot.runtime import assert_transition, transition_allowed
from app.bot.tenant import TenantBotContract, TenantIsolationViolation, assert_tenant_access


def test_bot_lifecycle_allows_expected_start_stop_paths():
    assert transition_allowed("approved", "starting")
    assert transition_allowed("starting", "running")
    assert transition_allowed("running", "stopped")
    assert transition_allowed("failed", "starting")
    assert transition_allowed("suspended", "approved")


def test_bot_lifecycle_rejects_unsafe_path():
    assert not transition_allowed("pending", "running")
    with pytest.raises(ValueError, match="invalid bot lifecycle transition"):
        assert_transition("pending", "running")


def test_tenant_bot_contract_blocks_cross_tenant_access():
    contract = TenantBotContract(tenant_id=10, bot_instance_id=20)
    assert_tenant_access(contract, 10)
    with pytest.raises(TenantIsolationViolation, match="Cross-tenant access blocked"):
        assert_tenant_access(contract, 11)


def test_tenant_bot_contract_requires_positive_ids():
    with pytest.raises(ValueError, match="invalid tenant bot contract"):
        TenantBotContract(tenant_id=0, bot_instance_id=20).validate()
