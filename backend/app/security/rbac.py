PERMISSIONS = {
    "tenant.read",
    "tenant.write",
    "users.read",
    "products.read",
    "products.write",
    "orders.read",
    "payments.read",
    "payments.approve",
    "wallet.read",
    "wallet.write",
    "coupons.write",
    "referrals.read",
    "tickets.read",
    "tickets.reply",
    "bots.read",
    "bots.write",
    "audit.read",
    "reports.read",
    "settings.write",
    "admins.write",
}
ROLE_PERMISSIONS = {
    "Owner": PERMISSIONS,
    "Admin": PERMISSIONS - {"admins.write"},
    "Finance": {
        "payments.read",
        "payments.approve",
        "wallet.read",
        "wallet.write",
        "orders.read",
        "reports.read",
    },
    "Support": {"users.read", "tickets.read", "tickets.reply"},
    "Sales": {
        "users.read",
        "products.read",
        "products.write",
        "orders.read",
        "coupons.write",
        "referrals.read",
    },
    "Viewer": {
        "tenant.read",
        "users.read",
        "products.read",
        "orders.read",
        "payments.read",
        "wallet.read",
        "reports.read",
    },
}


def allowed(role, permission):
    return permission in ROLE_PERMISSIONS.get(role, set())
