from __future__ import annotations

from enum import StrEnum
from typing import Final

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import (
    Order,
    Permission,
    Plan,
    Product,
    Referral,
    ReferralTransaction,
    Role,
    RolePermission,
    Service,
    Tenant,
    TenantUser,
    TenantUserRole,
    User,
    Wallet,
)


class TenantBotSection(StrEnum):
    REGISTER = "tenant:register"
    STORE = "tenant:store"
    PLANS = "tenant:plans"
    PURCHASE = "tenant:purchase"
    PAYMENTS = "tenant:payments"
    WALLET = "tenant:wallet"
    MY_ORDERS = "tenant:orders"
    MY_SERVICES = "tenant:services"
    RENEW = "tenant:renew"
    EXPIRY = "tenant:expiry"
    COUPON = "tenant:coupon"
    REFERRAL = "tenant:referral"
    SUPPORT = "tenant:support"
    FAQ = "tenant:faq"
    MINI_APP = "tenant:mini_app"


class TenantAdminSection(StrEnum):
    DASHBOARD = "tenant_admin:dashboard"
    USERS = "tenant_admin:users"
    PRODUCTS = "tenant_admin:products"
    ORDERS = "tenant_admin:orders"
    PAYMENTS = "tenant_admin:payments"
    WALLET = "tenant_admin:wallet"
    COUPONS = "tenant_admin:coupons"
    REFERRAL = "tenant_admin:referral"
    SERVICES = "tenant_admin:services"
    REPORTS = "tenant_admin:reports"
    BROADCAST = "tenant_admin:broadcast"
    TICKETS = "tenant_admin:tickets"
    BRANDING = "tenant_admin:branding"
    ADMINS = "tenant_admin:admins"


class TenantIsolationViolation(RuntimeError):
    pass


class TenantBotContract:
    def __init__(self, tenant_id: int, bot_instance_id: int, mini_app_enabled: bool = True):
        self.tenant_id = int(tenant_id)
        self.bot_instance_id = int(bot_instance_id)
        self.mini_app_enabled = mini_app_enabled

    def validate(self) -> None:
        if self.tenant_id <= 0 or self.bot_instance_id <= 0:
            raise ValueError("invalid tenant bot contract")
        if not self.mini_app_enabled:
            raise ValueError("Tenant Mini App must be enabled")


def assert_tenant_access(contract: TenantBotContract, requested_tenant_id: int) -> None:
    contract.validate()
    if requested_tenant_id != contract.tenant_id:
        raise TenantIsolationViolation("Cross-tenant access blocked")


def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ فروشگاه", callback_data=TenantBotSection.STORE.value), InlineKeyboardButton("📦 پلن‌ها", callback_data=TenantBotSection.PLANS.value)],
        [InlineKeyboardButton("🛒 خرید", callback_data=TenantBotSection.PURCHASE.value), InlineKeyboardButton("💳 پرداخت", callback_data=TenantBotSection.PAYMENTS.value)],
        [InlineKeyboardButton("💰 کیف پول", callback_data=TenantBotSection.WALLET.value), InlineKeyboardButton("📋 سفارش‌های من", callback_data=TenantBotSection.MY_ORDERS.value)],
        [InlineKeyboardButton("🖥️ سرویس‌های من", callback_data=TenantBotSection.MY_SERVICES.value), InlineKeyboardButton("🔄 تمدید", callback_data=TenantBotSection.RENEW.value)],
        [InlineKeyboardButton("⏰ انقضا", callback_data=TenantBotSection.EXPIRY.value), InlineKeyboardButton("🎟️ کد تخفیف", callback_data=TenantBotSection.COUPON.value)],
        [InlineKeyboardButton("🎁 دعوت دوستان", callback_data=TenantBotSection.REFERRAL.value), InlineKeyboardButton("💬 پشتیبانی", callback_data=TenantBotSection.SUPPORT.value)],
        [InlineKeyboardButton("❓ FAQ", callback_data=TenantBotSection.FAQ.value), InlineKeyboardButton("🚀 Mini App", callback_data=TenantBotSection.MINI_APP.value)],
    ])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد", callback_data=TenantAdminSection.DASHBOARD.value), InlineKeyboardButton("👥 کاربران", callback_data=TenantAdminSection.USERS.value)],
        [InlineKeyboardButton("🛍️ محصولات", callback_data=TenantAdminSection.PRODUCTS.value), InlineKeyboardButton("📋 سفارش‌ها", callback_data=TenantAdminSection.ORDERS.value)],
        [InlineKeyboardButton("💳 پرداخت‌ها", callback_data=TenantAdminSection.PAYMENTS.value), InlineKeyboardButton("💰 کیف پول", callback_data=TenantAdminSection.WALLET.value)],
        [InlineKeyboardButton("🎟️ کوپن", callback_data=TenantAdminSection.COUPONS.value), InlineKeyboardButton("🎁 Referral", callback_data=TenantAdminSection.REFERRAL.value)],
        [InlineKeyboardButton("🖥️ سرویس‌ها", callback_data=TenantAdminSection.SERVICES.value), InlineKeyboardButton("📈 گزارش‌ها", callback_data=TenantAdminSection.REPORTS.value)],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data=TenantAdminSection.BROADCAST.value), InlineKeyboardButton("🎫 تیکت‌ها", callback_data=TenantAdminSection.TICKETS.value)],
        [InlineKeyboardButton("🎨 برند", callback_data=TenantAdminSection.BRANDING.value), InlineKeyboardButton("👑 مدیران", callback_data=TenantAdminSection.ADMINS.value)],
        [InlineKeyboardButton("👤 حالت کاربر", callback_data="tenant:home")],
    ])


async def _ensure_user(db, telegram_user) -> User:
    user = await db.scalar(select(User).where(User.telegram_id == telegram_user.id))
    if user is None:
        user = User(telegram_id=telegram_user.id, username=telegram_user.username, first_name=telegram_user.first_name)
        db.add(user)
        await db.flush()
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
    return user


async def _ensure_membership(db, tenant_id: int, user_id: int) -> None:
    membership = await db.scalar(select(TenantUser).where(TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id))
    if membership is None:
        db.add(TenantUser(tenant_id=tenant_id, user_id=user_id, status="active"))
    elif membership.status != "active":
        membership.status = "active"


async def _tenant_access(db, tenant_id: int, telegram_id: int) -> tuple[bool, set[str], str | None]:
    result = await db.execute(
        select(Role.name, Permission.key)
        .join(TenantUserRole, TenantUserRole.role_id == Role.id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .join(User, User.id == TenantUserRole.user_id)
        .where(TenantUserRole.tenant_id == tenant_id, User.telegram_id == telegram_id)
    )
    rows = result.all()
    role_names = {name for name, _ in rows}
    permissions = {key for _, key in rows if key}
    admin_roles = {"Owner", "Admin", "Finance", "Support", "Sales", "Viewer"}
    role = next((name for name in role_names if name in admin_roles), None)
    return role is not None, permissions, role


async def _user_id_for_telegram(db, telegram_id: int) -> int | None:
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    return user.id if user else None


async def _tenant_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        tenant = await db.get(Tenant, tenant_id)
        if tenant is None or tenant.status != "active":
            await update.message.reply_text("⛔ این فروشگاه در حال حاضر فعال نیست.")
            return
        user = await _ensure_user(db, update.effective_user)
        await _ensure_membership(db, tenant_id, user.id)
        await db.commit()
        is_admin, _, role = await _tenant_access(db, tenant_id, update.effective_user.id)
        name = tenant.name
    if is_admin:
        await update.message.reply_text(f"👑 پنل مدیریت {name}\n\nنقش شما: {role}\nاز منوی مدیریت استفاده کنید.", reply_markup=admin_menu())
    else:
        await update.message.reply_text(f"👋 به {name} خوش آمدید.\n\nاز منوی زیر سرویس موردنظر را انتخاب کنید.", reply_markup=user_menu())


async def _admin_callback(query, context: ContextTypes.DEFAULT_TYPE, data: str) -> bool:
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        is_admin, permissions, role = await _tenant_access(db, tenant_id, query.from_user.id)
        if not is_admin:
            await query.answer("⛔ دسترسی مدیریتی ندارید.", show_alert=True)
            return True
        if data == TenantAdminSection.DASHBOARD.value:
            users = await db.scalar(select(func.count()).select_from(TenantUser).where(TenantUser.tenant_id == tenant_id, TenantUser.status == "active")) or 0
            products = await db.scalar(select(func.count()).select_from(Product).where(Product.tenant_id == tenant_id, Product.active.is_(True))) or 0
            orders = await db.scalar(select(func.count()).select_from(Order).where(Order.tenant_id == tenant_id)) or 0
            paid = await db.scalar(select(func.count()).select_from(Order).where(Order.tenant_id == tenant_id, Order.status == "paid")) or 0
            services = await db.scalar(select(func.count()).select_from(Service).where(Service.tenant_id == tenant_id, Service.status == "active")) or 0
            revenue = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.tenant_id == tenant_id, Order.status == "paid")) or 0
            text = f"📊 داشبورد فروشگاه\n\n👥 کاربران فعال: {users}\n🛍️ محصولات فعال: {products}\n📋 کل سفارش‌ها: {orders}\n✅ سفارش‌های پرداخت‌شده: {paid}\n🖥️ سرویس‌های فعال: {services}\n💰 فروش ثبت‌شده: {revenue} تومان\n\n🔐 نقش: {role}"
            await query.edit_message_text(text, reply_markup=admin_menu())
            return True
        page_map = {
            TenantAdminSection.USERS.value: ("👥 مدیریت کاربران", "users.read"),
            TenantAdminSection.PRODUCTS.value: ("🛍️ مدیریت محصولات", "products.read"),
            TenantAdminSection.ORDERS.value: ("📋 مدیریت سفارش‌ها", "orders.read"),
            TenantAdminSection.PAYMENTS.value: ("💳 مدیریت پرداخت‌ها", "payments.read"),
            TenantAdminSection.WALLET.value: ("💰 مدیریت کیف پول", "wallet.read"),
            TenantAdminSection.COUPONS.value: ("🎟️ مدیریت کوپن‌ها", "coupons.read"),
            TenantAdminSection.REFERRAL.value: ("🎁 مدیریت Referral", "referrals.read"),
            TenantAdminSection.SERVICES.value: ("🖥️ مدیریت سرویس‌ها", "services.read"),
            TenantAdminSection.REPORTS.value: ("📈 گزارش‌ها", "reports.read"),
            TenantAdminSection.BROADCAST.value: ("📢 پیام همگانی", "settings.write"),
            TenantAdminSection.TICKETS.value: ("🎫 تیکت‌ها", "tickets.read"),
            TenantAdminSection.BRANDING.value: ("🎨 برند و تنظیمات", "settings.read"),
            TenantAdminSection.ADMINS.value: ("👑 مدیران و نقش‌ها", "admins.read"),
        }
        if data not in page_map:
            return False
        title, permission = page_map[data]
        if permission not in permissions and role not in {"Owner", "Admin"}:
            await query.answer("⛔ این عملیات برای نقش شما مجاز نیست.", show_alert=True)
            return True
        url = f"{settings.mini_app_url.rstrip('/')}?tenant_id={tenant_id}&page=admin&section={data.split(':', 1)[1]}"
        await query.edit_message_text(f"{title}\n\nبرای مدیریت کامل این بخش، Mini App مدیریتی را باز کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 باز کردن بخش مدیریت", web_app=WebAppInfo(url=url))], [InlineKeyboardButton("⬅️ پنل مدیریت", callback_data=TenantAdminSection.DASHBOARD.value)]]))
        return True


async def _callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    tenant_id = int(context.bot_data["tenant_id"])
    contract = context.bot_data["contract"]
    assert_tenant_access(contract, tenant_id)
    data = query.data or ""
    if data.startswith("tenant_admin:") and await _admin_callback(query, context, data):
        return

    if data in {TenantBotSection.STORE.value, TenantBotSection.PLANS.value}:
        async with SessionLocal() as db:
            rows = await db.execute(select(Product, Plan).join(Plan, Plan.product_id == Product.id).where(Product.tenant_id == tenant_id, Product.active.is_(True), Plan.active.is_(True)).order_by(Product.id, Plan.price).limit(30))
            items = rows.all()
        if not items:
            await query.edit_message_text("🛍️ فعلاً محصول فعالی وجود ندارد.", reply_markup=user_menu())
            return
        buttons = [[InlineKeyboardButton(f"{product.name} — {plan.name} | {plan.price} تومان", callback_data=f"tenant:plan:{plan.id}")] for product, plan in items]
        buttons.append([InlineKeyboardButton("🚀 خرید امن در Mini App", web_app=WebAppInfo(url=f"{settings.mini_app_url.rstrip('/')}?tenant_id={tenant_id}"))])
        buttons.append([InlineKeyboardButton("⬅️ منو", callback_data="tenant:home")])
        await query.edit_message_text("🛍️ محصولات و پلن‌های فعال:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("tenant:plan:"):
        try:
            plan_id = int(data.rsplit(":", 1)[1])
        except ValueError:
            await query.answer("پلن نامعتبر است.", show_alert=True)
            return
        async with SessionLocal() as db:
            row = await db.execute(select(Product, Plan).join(Plan, Plan.product_id == Product.id).where(Product.tenant_id == tenant_id, Plan.id == plan_id, Product.active.is_(True), Plan.active.is_(True)))
            item = row.first()
        if not item:
            await query.answer("پلن پیدا نشد.", show_alert=True)
            return
        product, plan = item
        url = f"{settings.mini_app_url.rstrip('/')}?tenant_id={tenant_id}&plan_id={plan.id}"
        await query.edit_message_text(f"📦 {product.name}\n\nپلن: {plan.name}\n💰 {plan.price} تومان\n⏱ {plan.duration_days} روز\n📊 حجم: {plan.quota_gb or 'نامحدود'} GB", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ادامه خرید", web_app=WebAppInfo(url=url))], [InlineKeyboardButton("⬅️ بازگشت", callback_data=TenantBotSection.STORE.value)]]))
        return

    if data == TenantBotSection.MY_ORDERS.value:
        async with SessionLocal() as db:
            user_id = await _user_id_for_telegram(db, query.from_user.id)
            orders = list((await db.scalars(select(Order).where(Order.tenant_id == tenant_id, Order.user_id == user_id).order_by(Order.id.desc()).limit(15))).all()) if user_id else []
        text = "📋 هنوز سفارشی ندارید." if not orders else "📋 سفارش‌های من\n\n" + "\n".join(f"• #{item.id} — {item.status} — {item.total} تومان" for item in orders)
        await query.edit_message_text(text, reply_markup=user_menu())
        return

    if data == TenantBotSection.MY_SERVICES.value:
        async with SessionLocal() as db:
            user_id = await _user_id_for_telegram(db, query.from_user.id)
            services = list((await db.scalars(select(Service).where(Service.tenant_id == tenant_id, Service.user_id == user_id).order_by(Service.id.desc()).limit(20))).all()) if user_id else []
        text = "🖥️ هنوز سرویسی ندارید." if not services else "🖥️ سرویس‌های من\n\n" + "\n".join(f"• #{service.id} — {service.status} — انقضا: {service.expires_at or '—'}" for service in services)
        await query.edit_message_text(text, reply_markup=user_menu())
        return

    if data == TenantBotSection.WALLET.value:
        async with SessionLocal() as db:
            user_id = await _user_id_for_telegram(db, query.from_user.id)
            wallet = await db.scalar(select(Wallet).where(Wallet.tenant_id == tenant_id, Wallet.user_id == user_id)) if user_id else None
        balance = wallet.balance if wallet else 0
        await query.edit_message_text(f"💰 موجودی کیف پول شما: {balance} تومان\n\nبرای شارژ یا مشاهده تراکنش‌ها Mini App را باز کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 کیف پول", web_app=WebAppInfo(url=f"{settings.mini_app_url.rstrip('/')}?tenant_id={tenant_id}&page=wallet"))], [InlineKeyboardButton("⬅️ منو", callback_data="tenant:home")]]))
        return

    if data == TenantBotSection.REFERRAL.value:
        async with SessionLocal() as db:
            user_id = await _user_id_for_telegram(db, query.from_user.id)
            referral = await db.scalar(select(Referral).where(Referral.tenant_id == tenant_id, Referral.inviter_user_id == user_id).order_by(Referral.id.asc())) if user_id else None
            earnings = (await db.scalar(select(func.coalesce(func.sum(ReferralTransaction.amount), 0)).where(ReferralTransaction.tenant_id == tenant_id, ReferralTransaction.referral_id == referral.id)) or 0) if referral else 0
        text = f"🎁 کد دعوت شما: {referral.code}\n💰 کمیسیون ثبت‌شده: {earnings} تومان" if referral else "🎁 هنوز لینک دعوت فعالی برای شما ثبت نشده است."
        await query.edit_message_text(text, reply_markup=user_menu())
        return

    if data == TenantBotSection.MINI_APP.value:
        url = f"{settings.mini_app_url.rstrip('/')}?tenant_id={tenant_id}"
        await query.edit_message_text("🚀 مدیریت کامل خرید، پرداخت، کیف پول و سرویس‌ها در Mini App امن انجام می‌شود.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 باز کردن Mini App", web_app=WebAppInfo(url=url))], [InlineKeyboardButton("⬅️ منو", callback_data="tenant:home")]]))
        return

    labels = {
        TenantBotSection.PAYMENTS.value: "💳 پرداخت امن از طریق Mini App انجام می‌شود.",
        TenantBotSection.RENEW.value: "🔄 سرویس خود را از بخش سرویس‌ها انتخاب و تمدید کنید.",
        TenantBotSection.EXPIRY.value: "⏰ وضعیت و تاریخ انقضای سرویس‌ها در بخش سرویس‌های من نمایش داده می‌شود.",
        TenantBotSection.COUPON.value: "🎟️ کد تخفیف را هنگام checkout در Mini App وارد کنید.",
        TenantBotSection.SUPPORT.value: "💬 پشتیبانی از طریق تیکت در Mini App انجام می‌شود.",
        TenantBotSection.FAQ.value: "❓ سوالات متداول و راهنمای استفاده در Mini App در دسترس است.",
        TenantBotSection.PURCHASE.value: "🛒 برای خرید، فروشگاه یا Mini App را باز کنید.",
    }
    if data == "tenant:home":
        await query.edit_message_text("منوی اصلی", reply_markup=user_menu())
    elif data in labels:
        await query.edit_message_text(labels[data], reply_markup=user_menu())


def build_tenant_application(*, token: str, tenant_id: int, bot_instance_id: int) -> Application:
    contract = TenantBotContract(tenant_id, bot_instance_id, True)
    contract.validate()
    application = Application.builder().token(token).build()
    application.bot_data["tenant_id"] = tenant_id
    application.bot_data["contract"] = contract
    application.add_handler(CommandHandler("start", _tenant_start))
    application.add_handler(CallbackQueryHandler(_callback))
    return application


def build_tenant_contract(tenant_id: int, bot_instance_id: int) -> TenantBotContract:
    contract = TenantBotContract(tenant_id, bot_instance_id, True)
    contract.validate()
    return contract


__all__: Final = [
    "TenantBotSection",
    "TenantAdminSection",
    "TenantBotContract",
    "TenantIsolationViolation",
    "assert_tenant_access",
    "user_menu",
    "admin_menu",
    "build_tenant_application",
    "build_tenant_contract",
]
