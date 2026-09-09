# Canonical permission vocabulary used by the API and admin UI.
PERMISSIONS = {
    "dashboard.read",
    "tenants.read",
    "tenants.write",
    "tenants.approve",
    "users.read",
    "users.write",
    "products.read",
    "products.write",
    "orders.read",
    "orders.write",
    "payments.read",
    "payments.verify",
    "payments.refund",
    "wallet.read",
    "wallet.write",
    "coupons.read",
    "coupons.write",
    "referrals.read",
    "referrals.write",
    "tickets.read",
    "tickets.reply",
    "bots.read",
    "bots.write",
    "audit.read",
    "reports.read",
    "settings.read",
    "settings.write",
    "admins.read",
    "admins.write",
}

ROLE_PERMISSIONS = {
    "Owner": PERMISSIONS,
    "Admin": PERMISSIONS - {"admins.write"},
    "Finance": {
        "dashboard.read",
        "orders.read",
        "payments.read",
        "payments.verify",
        "payments.refund",
        "wallet.read",
        "wallet.write",
        "reports.read",
    },
    "Support": {
        "dashboard.read",
        "users.read",
        "tickets.read",
        "tickets.reply",
        "orders.read",
        "services.read",
    },
    "Sales": {
        "dashboard.read",
        "users.read",
        "products.read",
        "products.write",
        "orders.read",
        "orders.write",
        "coupons.read",
        "coupons.write",
        "referrals.read",
        "referrals.write",
    },
    "Viewer": {
        "dashboard.read",
        "tenants.read",
        "users.read",
        "products.read",
        "orders.read",
        "payments.read",
        "wallet.read",
        "reports.read",
        "settings.read",
        "audit.read",
    },
}

# Backwards-compatible aliases for older modules while the API migrates fully.
PERMISSION_ALIASES = {
    "tenant.read": "tenants.read",
    "tenant.write": "tenants.write",
    "payments.approve": "payments.verify",
    "admins.manage": "admins.write",
}


def allowed(role: str | None, permission: str) -> bool:
    canonical = PERMISSION_ALIASES.get(permission, permission)
    return canonical in ROLE_PERMISSIONS.get(role or "", set())


def permissions_for_role(role: str | None) -> set[str]:
    return set(ROLE_PERMISSIONS.get(role or "", set()))
