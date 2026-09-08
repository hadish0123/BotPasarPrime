from __future__ import annotations

import os
from enum import StrEnum

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import (
    ApprovalRequest,
    BotInstance,
    Tenant,
)
from app.services.tenant_activation import (
    activate_approved_tenant,
    approve_tenant,
    reject_tenant,
)

OWNER_TELEGRAM_ID = settings.owner_telegram_id or 0


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


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👑 نمایندگان PRIMEVPN",
                    callback_data=CentralMenu.REPRESENTATIVES.value,
                )
            ],
            [
                InlineKeyboardButton(
                    "🖥️ پنل شخصی من",
                    callback_data=CentralMenu.PERSONAL_PANEL.value,
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 وضعیت درخواست من",
                    callback_data=CentralMenu.REQUEST_STATUS.value,
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 پشتیبانی",
                    callback_data=CentralMenu.SUPPORT.value,
                )
            ],
            [
                InlineKeyboardButton(
                    "❓ راهنما",
                    callback_data=CentralMenu.HELP.value,
                )
            ],
        ]
    )


def owner_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 داشبورد",
                    callback_data=CentralMenu.OWNER_DASHBOARD.value,
                ),
                InlineKeyboardButton(
                    "🆕 درخواست‌های جدید",
                    callback_data=CentralMenu.OWNER_REQUESTS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🏢 Tenantها",
                    callback_data=CentralMenu.OWNER_TENANTS.value,
                ),
                InlineKeyboardButton(
                    "👥 کاربران",
                    callback_data=CentralMenu.OWNER_USERS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🤖 ربات‌ها",
                    callback_data=CentralMenu.OWNER_BOTS.value,
                ),
                InlineKeyboardButton(
                    "💳 پرداخت‌ها",
                    callback_data=CentralMenu.OWNER_PAYMENTS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔌 سرورها/اتصال‌ها",
                    callback_data=CentralMenu.OWNER_CONNECTIONS.value,
                ),
                InlineKeyboardButton(
                    "📈 گزارش‌ها",
                    callback_data=CentralMenu.OWNER_REPORTS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔔 اعلان‌ها",
                    callback_data=CentralMenu.OWNER_NOTIFICATIONS.value,
                ),
                InlineKeyboardButton(
                    "⚙️ تنظیمات",
                    callback_data=CentralMenu.OWNER_SETTINGS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛡️ Audit Log",
                    callback_data=CentralMenu.OWNER_AUDIT.value,
                )
            ],
        ]
    )


def owner_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید",
                    callback_data=f"{OwnerAction.APPROVE.value}:{request_id}",
                ),
                InlineKeyboardButton(
                    "❌ رد",
                    callback_data=f"{OwnerAction.REJECT.value}:{request_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏸ تعلیق",
                    callback_data=f"{OwnerAction.SUSPEND.value}:{request_id}",
                ),
                InlineKeyboardButton(
                    "🟢 فعال‌سازی",
                    callback_data=f"{OwnerAction.ACTIVATE.value}:{request_id}",
                ),
            ],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not user:
        return

    text = "👋 به 3XSHOP خوش آمدید.\n\nاز منوی زیر مسیر موردنظر خود را انتخاب کنید:"

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=main_menu(),
        )


async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not user or not is_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ دسترسی غیرمجاز.")
        return

    if update.message:
        await update.message.reply_text(
            "👑 پنل مالک 3XSHOP\n\nتمام عملیات مدیریتی از این بخش انجام می‌شود.",
            reply_markup=owner_menu(),
        )


def _count(db, model, **filters) -> int:
    query = db.query(model)

    for key, value in filters.items():
        query = query.filter(getattr(model, key) == value)

    return query.count()


async def owner_dashboard(query) -> None:
    db = SessionLocal()

    try:
        tenants = _count(db, Tenant, is_deleted=False)
        pending = _count(db, ApprovalRequest, status="pending_review")
        bots = _count(db, BotInstance)

        text = (
            "📊 داشبورد مالک\n\n"
            f"🏢 Tenantها: {tenants}\n"
            f"🆕 درخواست‌های در انتظار: {pending}\n"
            f"🤖 ربات‌ها: {bots}\n"
        )

        await query.edit_message_text(
            text,
            reply_markup=owner_menu(),
        )
    finally:
        await db.close()


async def owner_requests(query) -> None:
    db = SessionLocal()

    try:
        approval_result = await db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending_review")
            .order_by(ApprovalRequest.created_at.asc())
            .limit(20)
        )
        requests = approval_result.scalars().all()

        if not requests:
            await query.edit_message_text(
                "🆕 درخواست جدیدی وجود ندارد.",
                reply_markup=owner_menu(),
            )
            return

        for approval_request in requests:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == approval_request.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()

            if tenant is None:
                continue

            path_label = (
                "👑 نماینده PRIMEVPN"
                if approval_request.path == "primevpn_representative"
                else "🖥️ پنل شخصی"
            )

            text = (
                "🆕 درخواست فعال‌سازی\n\n"
                f"🏢 Tenant: {tenant.name}\n"
                f"🔗 مسیر: {path_label}\n"
                f"📌 وضعیت: {approval_request.status}\n\n"
                "اطلاعات حساس در این پیام نمایش داده نمی‌شوند."
            )

            await query.message.reply_text(
                text,
                reply_markup=owner_request_keyboard(approval_request.id),
            )

        await query.edit_message_text(
            "🆕 درخواست‌های در انتظار بررسی در پیام‌های بالا نمایش داده شدند.",
            reply_markup=owner_menu(),
        )
    finally:
        await db.close()


async def owner_tenants(query) -> None:
    db = SessionLocal()

    try:
        result = await db.execute(
            select(Tenant)
            .where(Tenant.is_deleted.is_(False))
            .order_by(Tenant.created_at.desc())
            .limit(30)
        )
        tenants = result.scalars().all()

        if not tenants:
            text = "🏢 هیچ Tenant فعالی ثبت نشده است."
        else:
            lines = ["🏢 Tenantها\n"]

            for tenant in tenants:
                lines.append(f"• {tenant.name} — {tenant.status}")

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            reply_markup=owner_menu(),
        )
    finally:
        await db.close()


async def owner_bots(query) -> None:
    db = SessionLocal()

    try:
        result = await db.execute(select(BotInstance).order_by(BotInstance.id.desc()).limit(30))
        bots = result.scalars().all()

        if not bots:
            text = "🤖 هیچ Bot Instance ثبت نشده است."
        else:
            lines = ["🤖 ربات‌ها\n"]

            for bot in bots:
                lines.append(f"• {bot.name} — {bot.status}")

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            reply_markup=owner_menu(),
        )
    finally:
        await db.close()


async def placeholder_owner_section(query, title: str) -> None:
    await query.edit_message_text(
        f"{title}\n\n"
        "این بخش در معماری 3XSHOP تعریف شده و در مراحل مربوط به خودش "
        "به ماژول عملیاتی متصل می‌شود.",
        reply_markup=owner_menu(),
    )


async def handle_owner_action(
    query,
    action: str,
    request_id: int,
) -> None:
    if not is_owner(query.from_user.id):
        await query.answer("⛔ دسترسی غیرمجاز.", show_alert=True)
        return

    db = SessionLocal()

    try:
        approval_result = await db.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        )
        approval_request = approval_result.scalar_one_or_none()

        if approval_request is None:
            await query.answer(
                "درخواست پیدا نشد.",
                show_alert=True,
            )
            return

        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == approval_request.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None:
            await query.answer(
                "Tenant مربوط به درخواست پیدا نشد.",
                show_alert=True,
            )
            return

        if action == OwnerAction.APPROVE.value:
            if approval_request.status != "pending_review":
                await query.answer(
                    "این درخواست قبلاً بررسی شده است.",
                    show_alert=True,
                )
                return

            await approve_tenant(
                db,
                approval_request.id,
            )
            await db.commit()

            await query.answer(
                "درخواست تأیید شد.",
                show_alert=False,
            )

            await query.edit_message_text(
                f"✅ درخواست Tenant «{tenant.name}» تأیید شد.\n\n"
                "برای فعال‌سازی نهایی، عملیات Activation انجام می‌شود.",
                reply_markup=owner_menu(),
            )

        elif action == OwnerAction.REJECT.value:
            if approval_request.status != "pending_review":
                await query.answer(
                    "این درخواست قبلاً بررسی شده است.",
                    show_alert=True,
                )
                return

            await reject_tenant(
                db,
                approval_request.id,
                note="Rejected by platform owner",
            )
            await db.commit()

            await query.answer("درخواست رد شد.")

            await query.edit_message_text(
                f"❌ درخواست Tenant «{tenant.name}» رد شد.",
                reply_markup=owner_menu(),
            )

        elif action == OwnerAction.ACTIVATE.value:
            if tenant.status != "approved":
                await query.answer(
                    "Tenant باید ابتدا تأیید شود.",
                    show_alert=True,
                )
                return

            await activate_approved_tenant(
                db,
                tenant.id,
            )
            await db.commit()

            await query.answer("Tenant فعال شد.")

            await query.edit_message_text(
                f"🟢 Tenant «{tenant.name}» فعال شد.",
                reply_markup=owner_menu(),
            )

        elif action == OwnerAction.SUSPEND.value:
            tenant.status = "suspended"
            await db.commit()

            await query.answer("Tenant تعلیق شد.")

            await query.edit_message_text(
                f"⏸ Tenant «{tenant.name}» تعلیق شد.",
                reply_markup=owner_menu(),
            )

        elif action == "owner:deactivate":
            tenant.status = "inactive"
            await db.commit()

            await query.answer("Tenant غیرفعال شد.")

            await query.edit_message_text(
                f"🔴 Tenant «{tenant.name}» غیرفعال شد.",
                reply_markup=owner_menu(),
            )

    except Exception:  # noqa: BLE001 - Telegram handler boundary must fail closed
        await db.rollback()
        await query.answer(
            "عملیات انجام نشد؛ خطای داخلی رخ داد.",
            show_alert=True,
        )
    finally:
        await db.close()


async def callback_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    if data.startswith("owner:approve:"):
        await handle_owner_action(
            query,
            OwnerAction.APPROVE.value,
            int(data.rsplit(":", 1)[1]),
        )
        return

    if data.startswith("owner:reject:"):
        await handle_owner_action(
            query,
            OwnerAction.REJECT.value,
            int(data.rsplit(":", 1)[1]),
        )
        return

    if data.startswith("owner:suspend:"):
        await handle_owner_action(
            query,
            OwnerAction.SUSPEND.value,
            int(data.rsplit(":", 1)[1]),
        )
        return

    if data.startswith("owner:activate:"):
        await handle_owner_action(
            query,
            OwnerAction.ACTIVATE.value,
            int(data.rsplit(":", 1)[1]),
        )
        return

    if data == CentralMenu.REPRESENTATIVES.value:
        await query.edit_message_text(
            "👑 نمایندگان PRIMEVPN\n\n"
            "در این مسیر، اطلاعات اتصال PasarGuard و اطلاعات ربات "
            "اختصاصی شما دریافت و پس از بررسی مالک فعال می‌شود.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="central:home",
                        )
                    ]
                ]
            ),
        )
        return

    if data == CentralMenu.PERSONAL_PANEL.value:
        await query.edit_message_text(
            "🖥️ پنل شخصی من\n\n"
            "برای پنل شخصی، اطلاعات اتصال PasarGuard خودتان را ثبت "
            "و هزینه فعال‌سازی یک‌باره را پرداخت می‌کنید.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="central:home",
                        )
                    ]
                ]
            ),
        )
        return

    if data == CentralMenu.REQUEST_STATUS.value:
        await query.edit_message_text(
            "📋 وضعیت درخواست من\n\n"
            "درخواست‌های شما بر اساس Telegram ID شناسایی و وضعیت "
            "آن‌ها نمایش داده خواهد شد.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="central:home",
                        )
                    ]
                ]
            ),
        )
        return

    if data == CentralMenu.SUPPORT.value:
        await query.edit_message_text(
            "💬 پشتیبانی\n\nبرای ارتباط با پشتیبانی، درخواست خود را ارسال کنید.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="central:home",
                        )
                    ]
                ]
            ),
        )
        return

    if data == CentralMenu.HELP.value:
        await query.edit_message_text(
            "❓ راهنما\n\n"
            "👑 نمایندگان PRIMEVPN: اتصال به زیرساخت مرکزی\n"
            "🖥️ پنل شخصی: اتصال به PasarGuard شخصی شما\n"
            "📋 وضعیت درخواست: مشاهده وضعیت فعال‌سازی\n"
            "💬 پشتیبانی: ارتباط با پشتیبانی",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ بازگشت",
                            callback_data="central:home",
                        )
                    ]
                ]
            ),
        )
        return

    if data == "central:home":
        await query.edit_message_text(
            "منوی اصلی 3XSHOP",
            reply_markup=main_menu(),
        )
        return

    if not is_owner(query.from_user.id):
        await query.answer(
            "⛔ دسترسی مالک موردنیاز است.",
            show_alert=True,
        )
        return

    if data == CentralMenu.OWNER_DASHBOARD.value:
        await owner_dashboard(query)
    elif data == CentralMenu.OWNER_REQUESTS.value:
        await owner_requests(query)
    elif data == CentralMenu.OWNER_TENANTS.value:
        await owner_tenants(query)
    elif data == CentralMenu.OWNER_USERS.value:
        await placeholder_owner_section(
            query,
            "👥 کاربران",
        )
    elif data == CentralMenu.OWNER_BOTS.value:
        await owner_bots(query)
    elif data == CentralMenu.OWNER_PAYMENTS.value:
        await placeholder_owner_section(
            query,
            "💳 پرداخت‌ها",
        )
    elif data == CentralMenu.OWNER_CONNECTIONS.value:
        await placeholder_owner_section(
            query,
            "🔌 سرورها/اتصال‌ها",
        )
    elif data == CentralMenu.OWNER_REPORTS.value:
        await placeholder_owner_section(
            query,
            "📈 گزارش‌ها",
        )
    elif data == CentralMenu.OWNER_NOTIFICATIONS.value:
        await placeholder_owner_section(
            query,
            "🔔 اعلان‌ها",
        )
    elif data == CentralMenu.OWNER_SETTINGS.value:
        await placeholder_owner_section(
            query,
            "⚙️ تنظیمات",
        )
    elif data == CentralMenu.OWNER_AUDIT.value:
        await placeholder_owner_section(
            query,
            "🛡️ Audit Log",
        )


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("owner", owner_command))
    application.add_handler(CallbackQueryHandler(callback_router))

    return application


def main() -> None:
    token = os.getenv("CENTRAL_BOT_TOKEN")

    if not token:
        raise RuntimeError("CENTRAL_BOT_TOKEN is not configured")

    if OWNER_TELEGRAM_ID <= 0:
        raise RuntimeError("OWNER_TELEGRAM_ID is not configured")

    application = build_application(token)

    print("3XSHOP CENTRAL BOT: READY")
    print("OWNER_ACCESS: ENABLED")
    print("OWNER_APPROVAL: REQUIRED")
    print("SECRETS_IN_MESSAGES: BLOCKED")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
