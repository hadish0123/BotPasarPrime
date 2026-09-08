from __future__ import annotations

from dataclasses import dataclass

REQUIRED_TABLES = (
    "tenants",
    "tenant_credentials",
    "tenant_branding",
    "bots",
    "users",
    "tenant_users",
    "roles",
    "permissions",
    "role_permissions",
    "user_roles",
    "products",
    "plans",
    "orders",
    "payments",
    "wallets",
    "wallet_transactions",
    "coupons",
    "referrals",
    "services",
    "tickets",
    "notifications",
    "broadcasts",
    "audit_logs",
    "settings",
)

REQUIRED_TENANT_SCOPED_TABLES = (
    "tenant_credentials",
    "tenant_branding",
    "bots",
    "tenant_users",
    "products",
    "plans",
    "orders",
    "payments",
    "wallets",
    "wallet_transactions",
    "coupons",
    "referrals",
    "services",
    "tickets",
    "notifications",
    "broadcasts",
    "audit_logs",
)


@dataclass(frozen=True)
class DataModelContract:
    tables: tuple[str, ...]
    tenant_scoped_tables: tuple[str, ...]
    foreign_keys_required: bool = True
    unique_constraints_required: bool = True
    indexes_required: bool = True
    statuses_in_migrations: bool = True


DATA_MODEL_CONTRACT = DataModelContract(
    tables=REQUIRED_TABLES,
    tenant_scoped_tables=REQUIRED_TENANT_SCOPED_TABLES,
)


def validate_table_names(existing_tables: set[str]) -> list[str]:
    return [table for table in REQUIRED_TABLES if table not in existing_tables]
