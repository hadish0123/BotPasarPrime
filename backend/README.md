# 3XSHOP

3XSHOP is a multi-tenant Telegram shop platform.

## Architecture

- app/bot
- app/miniapp
- app/api
- app/core
- app/models
- app/repositories
- app/services
- app/connectors/pasarguard
- app/workers
- app/security
- app/tasks
- migrations
- tests
- web
- scripts

## Principles

- Multi-tenant isolation
- Encrypted tenant credentials
- PasarGuard as an external connector
- Transactional financial operations
- Idempotent payments and orders
- Secure bot isolation
- No real credentials in source control
- Modular and testable production code

Database migrations are managed with Alembic.
