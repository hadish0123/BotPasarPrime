from __future__ import annotations

import os
from enum import StrEnum

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, Application

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import ApprovalRequest, BotInstance, Tenant
from app.services.tenant_activation import activate_approved_tenant, approve_tenant, get_latest_activation, reject_tenant

OWNER_TELEGRAM_ID = settings.owner_telegram_id or 0
_central_application: Application | None = None


class CentralMenu(StrEnum):
    REPRESENTATIVES = "central:representatives"
    PERSONAL_PANEL = "central:personal"
    REQUEST_STATUS = "central:request_status"
    SUPPORT = "central:support"
    HELP = "central:help"
    OWNER_DASHBOARD = "owner:dashboard"
    OWNER_REQUESTS = "owner:requests"
    OWNER_TENANTS = "owner:tenants"
    OWNER_USERS = "owner:users"
    OWNER_BOTS = "owner:bots"
    OWNER_PAYMENTS = "owner:payments"
    OWNER_CONNECTIONS = "owner:connections"
    OWNER_REPORTS = "owner:reports"
    OWNER_NOTIFICATIONS = "owner:notifications"
    OWNER_SETTINGS = "owner:settings"
    OWNER_AUDIT = "owner:audit"


class OwnerAction(StrEnum):
    APPROVE = "owner:approve"
    REJECT = "owner:reject"
    SUSPEND = "owner:suspend"
    ACTIVATE = "owner:activate"
    DEACTIVATE = "owner:deactivate"


def is_owner(user_id: int) -> bool:
    return OWNER_TELEGRAM_ID > 0 and user_id == OWNER_TELEGRAM_ID


def _web_app(path: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🚀 باز کردن فرم امن", web_app=WebAppInfo(url=f"{settings.mini_app_url.rstrip('/')}?mode=onboarding&path={path}"))], [InlineKeyboardButton("⬅️ بازگشت", callback_data="central:home")]])


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 ثبت نماینده PRIMEVPN", callback_data=CentralMenu.REPRESENTATIVES.value)],
        [InlineKeyboardButton("🖥️ ساخت پنل شخصی", callback_data=CentralMenu.PERSONAL_PANEL.value)],
        [InlineKeyboardButton("📋 وضعیت درخواست من", callback_data=CentralMenu.REQUEST_STATUS.value)],
        [InlineKeyboardButton("💬 پشتیبانی", callback_data=CentralMenu.SUPPORT.value)],
        [InlineKeyboardButton("❓ راهنما", callback_data=CentralMenu.HELP.value)],
    ])


def owner_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد", callback_data=CentralMenu.OWNER_DASHBOARD.value), InlineKeyboardButton("🆕 درخواست‌ها", callback_data=CentralMenu.OWNER_REQUESTS.value)],
        [InlineKeyboardButton("🏢 Tenantها", callback_data=CentralMenu.OWNER_TENANTS.value), InlineKeyboardButton("👥 کاربران", callback_data=CentralMenu.OWNER_USERS.value)],
        [InlineKeyboardButton("🤖 ربات‌ها", callback_data=CentralMenu.OWNER_BOTS.value), InlineKeyboardButton("💳 پرداخت‌ها", callback_data=CentralMenu.OWNER_PAYMENTS.value)],
        [InlineKeyboardButton("🔌 اتصال‌ها", callback_data=CentralMenu.OWNER_CONNECTIONS.value), InlineKeyboardButton("📈 گزارش‌ها", callback_data=CentralMenu.OWNER_REPORTS.value)],
        [InlineKeyboardButton("🔔 اعلان‌ها", callback_data=CentralMenu.OWNER_NOTIFICATIONS.value), InlineKeyboardButton("⚙️ تنظیمات", callback_data=CentralMenu.OWNER_SETTINGS.value)],
        [InlineKeyboardButton("🛡️ Audit Log", callback_data=CentralMenu.OWNER_AUDIT.value)],
    ])


def owner_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید", callback_data=f"owner:approve:{request_id}"), InlineKeyboardButton("❌ رد", callback_data=f"owner:reject:{request_id}")],
        [InlineKeyboardButton("⏸ تعلیق", callback_data=f"owner:suspend:{request_id}"), InlineKeyboardButton("🟢 فعال‌سازی", callback_data=f"owner:activate:{request_id}")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user and update.message:
        await update.message.reply_text("👋 به 3XSHOP خوش آمدید.", reply_markup=owner_menu() if is_owner(user.id) else main_menu())


async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ دسترسی غیرمجاز.")
        return
    if update.message:
        await update.message.reply_text("👑 پنل مالک 3XSHOP", reply_markup=owner_menu())


async def owner_dashboard(query) -> None:
    async with SessionLocal() as db:
        tenants = await db.scalar(select(func.count(Tenant.id)).where(Tenant.is_deleted.is_(False))) or 0
        pending = await db.scalar(select(func.count(ApprovalRequest.id)).where(ApprovalRequest.status == "pending_review")) or 0
        bots = await db.scalar(select(func.count(BotInstance.id))) or 0
    await query.edit_message_text(f"📊 داشبورد مالک\n\n🏢 Tenantها: {tenants}\n🆕 درخواست‌های در انتظار: {pending}\n🤖 ربات‌ها: {bots}", reply_markup=owner_menu())


async def owner_requests(query) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(ApprovalRequest).where(ApprovalRequest.status == "pending_review").order_by(ApprovalRequest.created_at.asc()).limit(20))
        requests = list(result.scalars().all())
        for item in requests:
            tenant = await db.get(Tenant, item.tenant_id)
            if tenant:
                await query.message.reply_text(f"🆕 درخواست فعال‌سازی\n\n🏢 {tenant.name}\n🔗 مسیر: {item.path}\n📌 وضعیت: {item.status}", reply_markup=owner_request_keyboard(item.id))
    await query.edit_message_text("🆕 درخواست‌های در انتظار در پیام‌های بالا نمایش داده شدند.", reply_markup=owner_menu())


async def owner_tenants(query) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_deleted.is_(False)).order_by(Tenant.created_at.desc()).limit(30))
        tenants = list(result.scalars().all())
    text = "🏢 Tenantها\n\n" + ("\n".join(f"• {t.name} — {t.status}" for t in tenants) if tenants else "موردی ثبت نشده است.")
    await query.edit_message_text(text, reply_markup=owner_menu())


async def owner_bots(query) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(BotInstance).order_by(BotInstance.id.desc()).limit(30))
        bots = list(result.scalars().all())
    text = "🤖 ربات‌ها\n\n" + ("\n".join(f"• {b.name} — {b.status}" for b in bots) if bots else "موردی ثبت نشده است.")
    await query.edit_message_text(text, reply_markup=owner_menu())


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    if data.startswith("owner:") and data.count(":") == 2:
        action, raw_id = data.rsplit(":", 1)
        if not is_owner(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز.", show_alert=True)
            return
        async with SessionLocal() as db:
            try:
                approval = await db.get(ApprovalRequest, int(raw_id))
                if approval is None:
                    raise ValueError("درخواست پیدا نشد")
                tenant = await db.get(Tenant, approval.tenant_id)
                if tenant is None:
                    raise ValueError("Tenant پیدا نشد")
                if action == "owner:approve":
                    await approve_tenant(db, approval.id)
                    await activate_approved_tenant(db, tenant.id)
                    await db.commit()
                    message = "✅ Tenant تأیید و فعال شد."
                elif action == "owner:reject":
                    await reject_tenant(db, approval.id, note="Rejected by platform owner")
                    await db.commit()
                    message = "❌ درخواست رد شد."
                elif action == "owner:activate":
                    await activate_approved_tenant(db, tenant.id)
                    await db.commit()
                    message = "🟢 Tenant فعال شد."
                elif action == "owner:suspend":
                    tenant.status = "suspended"
                    await db.commit()
                    message = "⏸ Tenant تعلیق شد."
                elif action == "owner:deactivate":
                    tenant.status = "inactive"
                    await db.commit()
                    message = "🔴 Tenant غیرفعال شد."
                else:
                    return
            except ValueError as exc:
                await db.rollback()
                await query.answer(str(exc), show_alert=True)
                return
        await query.edit_message_text(f"{message}\n\n🏢 {tenant.name}", reply_markup=owner_menu())
        return

    if data == CentralMenu.REPRESENTATIVES.value:
        await query.edit_message_text("👑 ثبت نماینده PRIMEVPN\n\nفرم امن را باز کنید؛ توکن‌ها داخل Telegram chat ارسال نمی‌شوند.", reply_markup=_web_app("representative"))
    elif data == CentralMenu.PERSONAL_PANEL.value:
        await query.edit_message_text("🖥️ ساخت پنل شخصی\n\nهزینه فعال‌سازی یک‌باره ۲۵۰٬۰۰۰ تومان است.", reply_markup=_web_app("personal_panel"))
    elif data == CentralMenu.REQUEST_STATUS.value:
        async with SessionLocal() as db:
            result = await get_latest_activation(db, query.from_user.id)
        if not result:
            text = "📋 هنوز درخواست فعالی برای شما ثبت نشده است."
        else:
            text = f"📋 وضعیت درخواست\n\n🏢 {result['tenant_name']}\n📌 Tenant: {result['tenant_status']}\n📝 Approval: {result['approval_status']}"
        await query.edit_message_text(text, reply_markup=main_menu())
    elif data == CentralMenu.SUPPORT.value:
        await query.edit_message_text("💬 پشتیبانی\n\nدرخواست خود را از طریق بخش تیکت ثبت کنید.", reply_markup=main_menu())
    elif data == CentralMenu.HELP.value:
        await query.edit_message_text("❓ راهنما\n\nثبت اطلاعات در Mini App امن انجام می‌شود و اطلاعات حساس داخل پیام ربات ذخیره یا نمایش داده نمی‌شود.", reply_markup=main_menu())
    elif data == "central:home":
        await query.edit_message_text("منوی اصلی 3XSHOP", reply_markup=main_menu())
    elif is_owner(query.from_user.id):
        if data == CentralMenu.OWNER_DASHBOARD.value:
            await owner_dashboard(query)
        elif data == CentralMenu.OWNER_REQUESTS.value:
            await owner_requests(query)
        elif data == CentralMenu.OWNER_TENANTS.value:
            await owner_tenants(query)
        elif data == CentralMenu.OWNER_BOTS.value:
            await owner_bots(query)
        else:
            await query.edit_message_text(f"{data}\n\nاین بخش از پنل مدیریتی قابل دسترسی است.", reply_markup=owner_menu())


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("owner", owner_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    return application


async def start_central_bot() -> None:
    global _central_application
    if _central_application is not None or not settings.central_bot_enabled:
        return
    if not settings.central_bot_token or OWNER_TELEGRAM_ID <= 0:
        raise RuntimeError("CENTRAL_BOT_TOKEN and OWNER_TELEGRAM_ID are required")
    application = build_application(settings.central_bot_token)
    await application.initialize()
    await application.start()
    if application.updater is None:
        await application.stop()
        await application.shutdown()
        raise RuntimeError("central bot updater is unavailable")
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    _central_application = application


async def stop_central_bot() -> None:
    global _central_application
    application = _central_application
    _central_application = None
    if application is None:
        return
    try:
        if application.updater and application.updater.running:
            await application.updater.stop()
        await application.stop()
    finally:
        await application.shutdown()


def main() -> None:
    token = os.getenv("CENTRAL_BOT_TOKEN")
    if not token or OWNER_TELEGRAM_ID <= 0:
        raise RuntimeError("CENTRAL_BOT_TOKEN and OWNER_TELEGRAM_ID are required")
    build_application(token).run_polling(allowed_updates=Update.ALL_TYPES)
