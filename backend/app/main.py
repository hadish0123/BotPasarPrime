from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.deps import bearer
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
from app.bot.runtime import runtime
from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if settings.app_env.lower() in {"production", "prod"}:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    await runtime.start_approved_bots()
    try:
        yield
    finally:
        await runtime.shutdown_all()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env.lower() not in {"production", "prod"} else None,
    redoc_url="/redoc" if settings.app_env.lower() not in {"production", "prod"} else None,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        item.strip()
        for item in settings.cors_origins.split(",")
        if item.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Telegram-Init-Data",
    ],
)


@app.get("/api/v1/me")
async def current_user(claims=Depends(bearer)):
    return {
        "user_id": claims.get("user_id") or claims.get("sub"),
        "telegram_id": claims.get("telegram_id"),
        "username": claims.get("username"),
        "tenant_id": claims.get("tenant_id"),
        "role": claims.get("role"),
        "permissions": claims.get("permissions", []),
        "is_platform_owner": bool(claims.get("is_platform_owner")),
    }


for router in (
    health_router,
    auth_router,
    tenants_router,
    products_router,
    orders_router,
    payments_router,
    wallet_router,
    coupons_router,
    tickets_router,
    admin_router,
    approvals_router,
    audit_router,
    bots_router,
    miniapp_router,
    referrals_router,
    users_router,
    settings_router,
    notifications_router,
    reports_router,
):
    app.include_router(router, prefix="/api/v1")
