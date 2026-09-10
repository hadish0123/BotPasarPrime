from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.db import SessionLocal
from app.models.entities import Plan, Product, User
from app.services.purchase import create_direct_payment, purchase_with_wallet
from app.services.shop import get_product
from app.services.tenant_activation import get_or_create_user


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


@dataclass(frozen=True)
class TenantBotContract:
    tenant_id: int
    bot_instance_id: int
    mini_app_enabled: bool = True

    def validate(self) -> None:
        if self.tenant_id <= 0:
            raise ValueError("Invalid tenant_id")
        if self.bot_instance_id <= 0:
            raise ValueError("Invalid bot_instance_id")
        if not self.mini_app_enabled:
            raise ValueError("Tenant Mini App must be enabled")


class TenantIsolationViolation(RuntimeError):
    pass


def assert_tenant_access(contract: TenantBotContract, requested_tenant_id: int) -> None:
    contract.validate()
    if requested_tenant_id != contract.tenant_id:
        raise TenantIsolationViolation("Cross-tenant access blocked")


def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛍️ فروشگاه", callback_data=TenantBotSection.STORE.value),
                InlineKeyboardButton("📦 پلن‌ها", callback_data=TenantBotSection.PLANS.value),
            ],
            [
                InlineKeyboardButton("🛒 خرید", callback_data=TenantBotSection.PURCHASE.value),
                InlineKeyboardButton("💳 پرداخت", callback_data=TenantBotSection.PAYMENTS.value),
            ],
            [
                InlineKeyboardButton("💰 کیف پول", callback_data=TenantBotSection.WALLET.value),
                InlineKeyboardButton("📋 سفارش‌های من", callback_data=TenantBotSection.MY_ORDERS.value),
            ],
            [
                InlineKeyboardButton("🖥️ سرویس‌های من", callback_data=TenantBotSection.MY_SERVICES.value),
                InlineKeyboardButton("🔄 تمدید", callback_data=TenantBotSection.RENEW.value),
            ],
            [
                InlineKeyboardButton("⏰ اعلان انقضا", callback_data=TenantBotSection.EXPIRY.value),
                InlineKeyboardButton("🎟️ کد تخفیف", callback_data=TenantBotSection.COUPON.value),
            ],
            [
                InlineKeyboardButton("🎁 دعوت دوستان", callback_data=TenantBotSection.REFERRAL.value),
                InlineKeyboardButton("💬 پشتیبانی", callback_data=TenantBotSection.SUPPORT.value),
            ],
            [
                InlineKeyboardButton("❓ FAQ", callback_data=TenantBotSection.FAQ.value),
                InlineKeyboardButton("🚀 باز کردن Mini App", callback_data=TenantBotSection.MINI_APP.value),
            ],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 داشبورد", callback_data=TenantAdminSection.DASHBOARD.value),
                InlineKeyboardButton("👥 کاربران", callback_data=TenantAdminSection.USERS.value),
            ],
            [
                InlineKeyboardButton("🛍️ محصولات و پلن‌ها", callback_data=TenantAdminSection.PRODUCTS.value),
                InlineKeyboardButton("📋 سفارش‌ها", callback_data=TenantAdminSection.ORDERS.value),
            ],
            [
                InlineKeyboardButton("💳 پرداخت‌ها", callback_data=TenantAdminSection.PAYMENTS.value),
                InlineKeyboardButton("💰 کیف پول", callback_data=TenantAdminSection.WALLET.value),
            ],
            [
                InlineKeyboardButton("🎟️ کوپن", callback_data=TenantAdminSection.COUPONS.value),
                InlineKeyboardButton("🎁 Referral", callback_data=TenantAdminSection.REFERRAL.value),
            ],
            [
                InlineKeyboardButton("🖥️ سرویس‌ها", callback_data=TenantAdminSection.SERVICES.value),
                InlineKeyboardButton("📈 گزارش‌ها", callback_data=TenantAdminSection.REPORTS.value),
            ],
            [
                InlineKeyboardButton("📢 پیام همگانی", callback_data=TenantAdminSection.BROADCAST.value),
                InlineKeyboardButton("🎫 تیکت‌ها", callback_data=TenantAdminSection.TICKETS.value),
            ],
            [
                InlineKeyboardButton("🎨 تنظیمات برند", callback_data=TenantAdminSection.BRANDING.value),
                InlineKeyboardButton("👑 مدیران و سطح دسترسی", callback_data=TenantAdminSection.ADMINS.value),
            ],
        ]
    )


async def _tenant_start(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "👋 خوش آمدید.\n\nاز منوی زیر سرویس موردنظر خود را انتخاب کنید.",
            reply_markup=user_menu(),
        )


async def _purchase_callback(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    tenant_id = int(context.application.bot_data["tenant_id"])
    telegram_id = int(query.from_user.id)
    data = query.data

    async with SessionLocal() as db:
        user = await get_or_create_user(
            db,
            telegram_id=telegram_id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
        )
        await db.commit()

        if data == TenantBotSection.PURCHASE.value:
            products = (
                await db.scalars(
                    select(Product).where(
                        Product.tenant_id == tenant_id,
                        Product.active.is_(True),
                    ).order_by(Product.id)
                )
            ).all()
            if not products:
                await query.edit_message_text("❌ فعلاً هیچ محصول فعالی برای خرید وجود ندارد.")
                return
            keyboard = [
                [InlineKeyboardButton(p.name, callback_data=f"purchase:product:{p.id}")]
                for p in products
            ]
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="purchase:back")])
            await query.edit_message_text("🛒 محصول موردنظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data == "purchase:back":
            await query.edit_message_text("منوی اصلی", reply_markup=user_menu())
            return

        if data.startswith("purchase:product:"):
            product_id = int(data.rsplit(":", 1)[1])
            product = await get_product(db, tenant_id, product_id)
            if not product:
                await query.edit_message_text("❌ محصول پیدا نشد.")
                return
            plans = (
                await db.scalars(
                    select(Plan).where(
                        Plan.product_id == product.id,
                        Plan.active.is_(True),
                    ).order_by(Plan.id)
                )
            ).all()
            if not plans:
                await query.edit_message_text("❌ برای این محصول پلن فعالی وجود ندارد.")
                return
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"{plan.name} | {plan.price} | {plan.duration_days} روز",
                        callback_data=f"purchase:plan:{plan.id}",
                    )
                ]
                for plan in plans
            ]
            await query.edit_message_text(
                f"📦 {product.name}\n\nپلن را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        if data.startswith("purchase:plan:"):
            plan_id = int(data.rsplit(":", 1)[1])
            plan = await db.scalar(
                select(Plan).where(Plan.id == plan_id, Plan.active.is_(True))
            )
            if not plan:
                await query.edit_message_text("❌ پلن پیدا نشد.")
                return
            context.user_data["purchase_plan_id"] = plan.id
            await query.edit_message_text(
                f"🧾 پلن: {plan.name}\n💰 مبلغ: {plan.price}\n⏳ مدت: {plan.duration_days} روز\n📦 حجم: {plan.quota_gb or 0} GB\n\nروش پرداخت را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("💰 پرداخت از کیف پول", callback_data=f"purchase:wallet:{plan.id}")],
                        [InlineKeyboardButton("💳 پرداخت مستقیم", callback_data=f"purchase:direct:{plan.id}")],
                    ]
                ),
            )
            return

        if data.startswith("purchase:wallet:"):
            plan_id = int(data.rsplit(":", 1)[1])
            key = f"tg:{telegram_id}:plan:{plan_id}"
            try:
                order, payment, service = await purchase_with_wallet(
                    db,
                    tenant_id=tenant_id,
                    user=user,
                    plan_id=plan_id,
                    idempotency_key=key,
                )
                await db.commit()
                subscription_url = service.metadata_json.get("subscription_url")
                await query.edit_message_text(
                    f"✅ خرید با موفقیت انجام شد.\n\n🧾 سفارش: #{order.id}\n💳 پرداخت: #{payment.id}\n\n🔗 لینک اشتراک:\n{subscription_url}",
                    disable_web_page_preview=True,
                )
            except Exception as exc:
                await db.rollback()
                await query.edit_message_text(f"❌ خرید انجام نشد.\n\n{type(exc).__name__}")
            return

        if data.startswith("purchase:direct:"):
            plan_id = int(data.rsplit(":", 1)[1])
            key = f"tg:{telegram_id}:direct:{plan_id}"
            try:
                order, payment = await create_direct_payment(
                    db,
                    tenant_id=tenant_id,
                    user=user,
                    plan_id=plan_id,
                    idempotency_key=key,
                )
                await db.commit()
                context.user_data["pending_payment_id"] = payment.id
                await query.edit_message_text(
                    f"💳 پرداخت مستقیم برای سفارش #{order.id} ایجاد شد.\n\nشناسه پرداخت: #{payment.id}\nمبلغ: {payment.amount}\n\nپس از پرداخت، شماره پیگیری/رسید را همینجا ارسال کنید تا پرداخت وارد مرحله بررسی شود.",
                )
            except Exception as exc:
                await db.rollback()
                await query.edit_message_text(f"❌ ایجاد پرداخت ناموفق بود.\n\n{type(exc).__name__}")
            return


async def _payment_reference(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment_id = context.user_data.get("pending_payment_id")
    if not payment_id or not update.message or not update.message.text:
        return
    reference = update.message.text.strip()
    if not 1 <= len(reference) <= 150:
        await update.message.reply_text("❌ شماره پیگیری معتبر نیست.")
        return

    tenant_id = int(context.application.bot_data["tenant_id"])
    async with SessionLocal() as db:
        from app.services.payments import get_payment, transition

        payment = await get_payment(db, tenant_id, int(payment_id))
        if not payment:
            context.user_data.pop("pending_payment_id", None)
            await update.message.reply_text("❌ پرداخت پیدا نشد.")
            return
        try:
            transition(payment, "submitted")
            payment.reference = reference
            await db.commit()
            context.user_data.pop("pending_payment_id", None)
            await update.message.reply_text(
                "✅ رسید ثبت شد و پرداخت برای بررسی ارسال شد. پس از تأیید، لینک اشتراک برای شما فعال می‌شود."
            )
        except ValueError as exc:
            await db.rollback()
            await update.message.reply_text(f"❌ وضعیت پرداخت قابل تغییر نیست: {exc}")


def build_tenant_application(*, token: str, tenant_id: int, bot_instance_id: int) -> Application:
    contract = TenantBotContract(
        tenant_id=int(tenant_id),
        bot_instance_id=int(bot_instance_id),
        mini_app_enabled=True,
    )
    contract.validate()

    application = Application.builder().token(token).build()
    application.bot_data["tenant_id"] = int(tenant_id)
    application.bot_data["bot_instance_id"] = int(bot_instance_id)

    application.add_handler(CommandHandler("start", _tenant_start))
    application.add_handler(
        CallbackQueryHandler(
            _purchase_callback,
            pattern=r"^(tenant:purchase|purchase:.*)$",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _payment_reference)
    )
    return application


def build_tenant_contract(tenant_id: int, bot_instance_id: int) -> TenantBotContract:
    contract = TenantBotContract(
        tenant_id=tenant_id,
        bot_instance_id=bot_instance_id,
        mini_app_enabled=True,
    )
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
