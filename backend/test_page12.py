from app.rbac import (
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLES,
    ROLE_PERMISSIONS,
    require_permission_key,
    require_same_tenant,
)


def main():
    expected_roles = {
        "Owner",
        "Admin",
        "Finance",
        "Support",
        "Sales",
        "Viewer",
    }

    assert set(DEFAULT_ROLES) == expected_roles

    required = {
        "users.read",
        "users.write",
        "orders.read",
        "payments.verify",
        "products.write",
        "settings.write",
        "admins.manage",
    }

    assert required.issubset(
        set(DEFAULT_PERMISSIONS)
    )

    for key in DEFAULT_PERMISSIONS:
        require_permission_key(key)

    assert (
        "admins.manage"
        in ROLE_PERMISSIONS["Owner"]
    )

    assert (
        "admins.manage"
        not in ROLE_PERMISSIONS["Admin"]
    )

    try:
        require_same_tenant(1, 2)
    except Exception:
        pass
    else:
        raise AssertionError(
            "CROSS_TENANT_OWNER_ACCESS_NOT_BLOCKED"
        )

    require_same_tenant(1, 1)

    from app.models.entities import (
        Permission,
        Role,
        RolePermission,
        TenantUserRole,
    )

    assert {
        "id",
        "key",
        "description",
    }.issubset(
        Permission.__table__.columns.keys()
    )

    assert {
        "tenant_id",
        "name",
        "is_system",
    }.issubset(
        Role.__table__.columns.keys()
    )

    assert {
        "role_id",
        "permission_id",
    }.issubset(
        RolePermission.__table__.columns.keys()
    )

    assert {
        "tenant_id",
        "user_id",
        "role_id",
    }.issubset(
        TenantUserRole.__table__.columns.keys()
    )

    print("PAGE 12 RBAC CONTRACT: OK")
    print("RBAC: ENABLED")
    print("ROLES: Owner,Admin,Finance,Support,Sales,Viewer")
    print("PERMISSION_KEYS: ENABLED")
    print("OWNER_TENANT_SCOPE: ENFORCED")
    print("CROSS_TENANT_ACCESS: BLOCKED")
    print("ROLE_PERMISSION_MAPPING: READY")
    print("TENANT_USER_ROLES: READY")
    print("PAGE 12 DATABASE CONTRACT: OK")


if __name__ == "__main__":
    main()
