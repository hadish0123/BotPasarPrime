# GitBook → Implementation map

1. 3XSHOP → architecture/onboarding foundations
2. معماری سیستم → `docs/architecture.md`
3. ثبت و فعال‌سازی Tenant → `app/services/onboarding.py`
4. ربات مرکزی → `app/bot/central.py`
5. ربات اختصاصی Tenant → `app/bot/tenant.py`
6. Telegram Mini App → `app/security/telegram_init_data.py`, `frontend/src/pages/miniapp/*`
7. چندمستاجری → `app/core/tenant.py`, tenant repositories
8. مدل داده → `app/models/entities.py`, Alembic migration
9. پرداخت → `app/services/payments.py`, adapters
10. فروشگاه و پلن‌ها → products/plans APIs and UI
11. کیف پول/کوپن/Referral → services + routers
12. مدیران/RBAC → `app/security/rbac.py`
13. PasarGuard → `app/connectors/pasarguard/*`
14. امنیت → `app/security/*`, middleware
15. API → `app/api/routers/*`
16. اعلان/Scheduler → `app/services/notifications.py`, `app/tasks/scheduler.py`
17. Audit/Reports → `app/services/audit.py`, reports router
18. Runtime → `app/bot/runtime.py`
19. Source structure → this repository
20. Test/quality → `tests/`
21. Deployment → Docker, env, docs
22. Acceptance → `docs/acceptance.md`
23. Store/plans related output → products/plans UI/API
