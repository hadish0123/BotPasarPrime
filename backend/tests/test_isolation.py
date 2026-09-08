def test_tenant_scope_is_required():
    from app.core.tenant import get_tenant

    try:
        get_tenant()
    except RuntimeError:
        assert True
    else:
        assert False
