# Architecture
Telegram users enter through Central Bot or Tenant Bot/Mini App. Requests reach FastAPI with an explicit tenant context. Domain services use tenant-scoped repositories. External PasarGuard access occurs only through the connector interface. Background workers handle expiry/notifications and idempotent jobs. Owner operations remain globally scoped and auditable.
