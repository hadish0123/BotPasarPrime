# 3XSHOP — Multi-Tenant Commerce & Service Platform

Comprehensive source implementation aligned with the 23-page PRIMEVPN GitBook specification.

## Architecture
- FastAPI + SQLAlchemy 2.x + Alembic backend
- React + TypeScript + Vite admin/tenant web UI
- Central Telegram bot and isolated tenant bot runtime boundaries
- Telegram Mini App with server-side `initData` validation
- Tenant-scoped repositories/services and RBAC
- Manual/payment-provider adapter boundary
- Immutable wallet ledger, coupons, referrals, tickets, notifications, audit
- Configuration-driven PasarGuard connector; no fake external endpoints and no real credentials

## Quick start
```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --app-dir backend --reload
```
Frontend:
```bash
cd frontend && npm install && npm run dev
```
Docker:
```bash
docker compose up --build
```

## Security
Never commit Telegram bot tokens, PasarGuard credentials, payment credentials, JWT secrets, or encryption keys. Bot tokens are encrypted at rest and masked in API responses/logs. Use a production secret manager.

## PasarGuard
The GitBook specifies an adapter boundary but does not provide a verified concrete PasarGuard API contract. The connector therefore exposes typed operations and configurable HTTP mappings rather than inventing endpoints. Configure mappings in the environment/tenant credential metadata after obtaining the real provider API documentation.

## Validation
The repository contains unit, API, security, isolation, payment, wallet, referral, coupon, onboarding, Mini App, runtime and connector tests. They are included as source; execution depends on the target environment and credentials.
