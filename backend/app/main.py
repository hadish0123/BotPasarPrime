from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.admin import r as admin_router
from app.api.routers.approvals import r as approvals_router
from app.api.routers.audit import r as audit_router
from app.api.routers.auth import r as auth_router
from app.api.routers.bots import r as bots_router
from app.api.routers.coupons import r as coupons_router
from app.api.routers.health import r as health_router
from app.api.routers.miniapp import r as miniapp_router
from app.api.routers.notifications import r as notifications_router
from app.api.routers.orders import r as orders_router
from app.api.routers.payments import r as payments_router
from app.api.routers.products import r as products_router
from app.api.routers.referrals import r as referrals_router
from app.api.routers.reports import r as reports_router
from app.api.routers.settings import r as settings_router
from app.api.routers.tenants import r as tenants_router
from app.api.routers.tickets import r as tickets_router
from app.api.routers.users import r as users_router
from app.api.routers.wallet import r as wallet_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(tenants_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(coupons_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(bots_router, prefix="/api/v1")
app.include_router(miniapp_router, prefix="/api/v1")
app.include_router(referrals_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
