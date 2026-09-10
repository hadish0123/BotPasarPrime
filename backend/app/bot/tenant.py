from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from uuid import uuid4

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.core.db import SessionLocal
from app.models.entities import Order, Plan, Product
from app.services.manual_payment import (
    get_manual_card_details,
    get_pending_manual_payment_for_user,
    get_tenant_owner_telegram_id,
    payment_customer,
    submit_manual_receipt,
    verify_manual_payment,
)
from app.services.purchase import create_direct_payment, fulfill_verified_payment, purchase_with_wallet
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
            [InlineKeyboardButton("🛍️ فروشگاه", callback_data=TenantBotSection.STORE.value), InlineKeyboardButton("📦 پلن‌ها", callback_data=TenantBotSection.PLANS.value)],
            [InlineKeyboardButton("🛒 خرید کانفیگ", callback_data=TenantBotSection.PURCHASE.value), InlineKeyboardButton("💳 پرداخت", callback_data=TenantBotSection.PAYMENTS.value)],
            [InlineKeyboardButton("💰 کیف پول", callback_data=TenantBotSection.WALLET.value), InlineKeyboardButton("📋 سفارش‌های من", callback_data=TenantBotSection.MY_ORDERS.value)],
            [InlineKeyboardButton("🖥️ سرویس‌های من", callback_data=TenantBotSection.MY_SERVICES.value), InlineKeyboardButton("🔄 تمدید", callback_data=TenantBotSection.RENEW.value)],
            [InlineKeyboardButton("⏰ اعلان انقضا", callback_data=TenantBotSection.EXPIRY.value), InlineKeyboardButton("🎟️ کد تخفیف", callback_data=TenantBotSection.COUPON.value)],
            [InlineKeyboardButton("🎁 دعوت دوستان", callback_data=TenantBotSection.REFERRAL.value), InlineKeyboardButton("💬 پشتیبانی", callback_data=TenantBotSection.SUPPORT.value)],
            [InlineKeyboardButton("❓ FAQ", callback_data=TenantBotSection.FAQ.value), InlineKeyboardButton("🚀 باز کردن Mini App", callback_data=TenantBotSection.MINI_APP.value)],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 داشبورد", callback_data=TenantAdminSection.DASHBOARD.value), InlineKeyboardButton("👥 کاربران", callback_data=TenantAdminSection.USERS.value)],
            [InlineKeyboardButton("🛍️ محصولات و پلن‌ها", callback_data=TenantAdminSection.PRODUCTS.value), InlineKeyboardButton("📋 سفارش‌ها", callback_data=TenantAdminSection.ORDERS.value)],
            [InlineKeyboardButton("💳 پرداخت‌ها", callback_data=TenantAdminSection.PAYMENTS.value), InlineKeyboardButton("💰 کیف پول", callback_data=TenantAdminSection.WALLET.value)],
            [InlineKeyboardButton("🎟️ کوپن", callback_data=TenantAdminSection.COUPONS.value), InlineKeyboardButton("🎁 Referral", callback_data=TenantAdminSection.REFERRAL.value)],
            [InlineKeyboardButton("🖥️ سرویس‌ها", callback_data=TenantAdminSection.SERVICES.value), InlineKeyboardButton("📈 گزارش‌ها", callback_data=TenantAdminSection.REPORTS.value)],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data=TenantAdminSection.BROADCAST.value), InlineKeyboardButton("🎫 تیکت‌ها", callback_data=TenantAdminSection.TICKETS.value)],
            [InlineKeyboardButton("🎨 تنظیمات برند", callback_data=TenantAdminSection.BRANDING.value), InlineKeyboardButton("👑 مدیران و سطح دسترسی", callback_data=TenantAdminSection.ADMINS.value)],
        ]
    )


def payment_review_keyboard(tenant_id: int, payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ تأیید و ارسال کانفیگ", callback_data=f"payment:approve:{tenant_id}:{payment_id}"),
            InlineKeyboardButton("❌ رد پرداخت", callback_data=f"payment:reject:{tenant_id}:{payment_id}"),
        ]]
    )


async def _tenant_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("👋 خوش آمدید.\n\nاز منوی زیر سرویس موردنظر خود را انتخاب کنید.", reply_markup=user_menu())


async def _purchase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    tenant_id = int(context.application.bot_data["tenant_id"])
    telegram_id = int(query.from_user.id)
    data = query.data

    async with SessionLocal() as db:
        user = await get_or_create_user(db, telegram_id=telegram_id, username=query.from_user.username, first_name=query.from_user.first_name)

        if data == TenantBotSection.PURCHASE.value:
            products = (await db.scalars(select(Product).where(Product.tenant_id == tenant_id, Product.active.is_(True)).order_by(Product.id))).all()
            if not products:
                await query.edit_message_text("❌ فعلاً هیچ محصول فعالی برای خرید وجود ندارد.", reply_markup=user_menu())
                return
            keyboard = [[InlineKeyboardButton(p.name, callback_data=f"purchase:product:{p.id}")] for p in products]
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
                await query.edit_message_text("❌ محصول پیدا نشد.", reply_markup=user_menu())
                return
            plans = (await db.scalars(select(Plan).where(Plan.product_id == product.id, Plan.active.is_(True)).order_by(Plan.id))).all()
            if not plans:
                await query.edit_message_text("❌ برای این محصول پلن فعالی وجود ندارد.", reply_markup=user_menu())
                return
            keyboard = [[InlineKeyboardButton(f"{plan.name} | {plan.price} تومان | {plan.duration_days} روز", callback_data=f"purchase:plan:{plan.id}")] for plan in plans]
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=TenantBotSection.PURCHASE.value)])
            await query.edit_message_text(f"📦 {product.name}\n\nپلن را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data.startswith("purchase:plan:"):
            plan_id = int(data.rsplit(":", 1)[1])
            plan = await db.scalar(select(Plan).where(Plan.id == plan_id, Plan.active.is_(True)))
            if not plan:
                await query.edit_message_text("❌ پلن پیدا نشد.", reply_markup=user_menu())
                return
            context.user_data["purchase_plan_id"] = plan.id
            await query.edit_message_text(
                f"🧾 پلن: {plan.name}\n💰 مبلغ: {plan.price} تومان\n⏳ مدت: {plan.duration_days} روز\n📦 حجم: {plan.quota_gb or 0} GB\n\nروش پرداخت را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 پرداخت از کیف پول", callback_data=f"purchase:wallet:{plan.id}")],
                    [InlineKeyboardButton("💳 پرداخت مستقیم با کارت", callback_data=f"purchase:direct:{plan.id}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data=TenantBotSection.PURCHASE.value)],
                ]),
            )
            return

        if data.startswith("purchase:wallet:"):
            plan_id = int(data.rsplit(":", 1)[1])
            try:
                key = f"tg:{telegram_id}:wallet:{uuid4().hex}"
                order, payment, service = await purchase_with_wallet(db, tenant_id=tenant_id, user=user, plan_id=plan_id, idempotency_key=key)
                await db.commit()
                subscription_url = service.metadata_json.get("subscription_url")
                await query.edit_message_text(f"✅ خرید با کیف پول با موفقیت انجام شد.\n\n🧾 سفارش: #{order.id}\n\n🔗 لینک اشتراک:\n{subscription_url}", disable_web_page_preview=True, reply_markup=user_menu())
            except Exception:
                await db.rollback()
                await query.edit_message_text("❌ خرید با کیف پول انجام نشد. موجودی یا اطلاعات سرویس را بررسی کنید.", reply_markup=user_menu())
            return

        if data.startswith("purchase:direct:"):
            plan_id = int(data.rsplit(":", 1)[1])
            try:
                card_number, card_holder = await get_manual_card_details(db)
                key = f"tg:{telegram_id}:manual:{uuid4().hex}"
                order, payment = await create_direct_payment(db, tenant_id=tenant_id, user=user, plan_id=plan_id, idempotency_key=key)
                await db.commit()
                holder_line = f"👤 به نام: {card_holder}\n" if card_holder else ""
                await query.edit_message_text(
                    f"💳 پرداخت مستقیم\n\n🧾 سفارش: #{order.id}\n💰 مبلغ قابل پرداخت: {payment.amount} تومان\n\n🏦 شماره کارت:\n`{card_number}`\n{holder_line}\n1️⃣ مبلغ دقیق بالا را واریز کنید.\n2️⃣ رسید تصویری پرداخت را همینجا ارسال کنید.\n3️⃣ رسید برای ادمین ارسال و پس از تأیید، کانفیگ و لینک اشتراک برای شما صادر می‌شود.\n\n⚠️ تا تأیید ادمین، سرویس فعال نمی‌شود.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=TenantBotSection.PURCHASE.value)]]),
                )
            except ValueError as exc:
                await db.rollback()
                if str(exc) == "manual_payment_card_not_configured":
                    await query.edit_message_text("❌ شماره کارت پرداخت هنوز توسط ادمین تنظیم نشده است.", reply_markup=user_menu())
                else:
                    await query.edit_message_text("❌ ایجاد پرداخت انجام نشد.", reply_markup=user_menu())
            except Exception:
                await db.rollback()
                await query.edit_message_text("❌ ایجاد پرداخت انجام نشد.", reply_markup=user_menu())
            return


async def _payment_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return
    tenant_id = int(context.application.bot_data["tenant_id"])
    telegram_id = int(update.effective_user.id)
    async with SessionLocal() as db:
        user = await get_or_create_user(db, telegram_id=telegram_id, username=update.effective_user.username, first_name=update.effective_user.first_name)
        payment = await get_pending_manual_payment_for_user(db, tenant_id=tenant_id, user_id=user.id)
        if not payment:
            await update.message.reply_text("ℹ️ پرداخت مستقیم در انتظار رسیدی از شما وجود ندارد.")
            return
        photo = update.message.photo[-1]
        caption = (update.message.caption or "").strip()
        reference = f"telegram:{photo.file_unique_id}"
        if caption:
            reference = f"{reference}|{caption[:70]}"
        try:
            payment = await submit_manual_receipt(db, tenant_id=tenant_id, user_id=user.id, receipt_reference=reference)
            owner_id = await get_tenant_owner_telegram_id(db, tenant_id)
            order = await db.scalar(select(Order).where(Order.id == payment.order_id, Order.tenant_id == tenant_id))
            await db.commit()
            await update.message.reply_text("✅ رسید دریافت شد و برای ادمین ارسال شد.\n\nپس از بررسی و تأیید، لینک اشتراک برای شما ارسال می‌شود.", reply_markup=user_menu())
            owner_caption = f"💳 رسید پرداخت جدید\n\n🏢 Tenant: {tenant_id}\n🧾 سفارش: #{order.id if order else payment.order_id}\n💰 مبلغ: {payment.amount} تومان\n👤 مشتری: @{update.effective_user.username or 'بدون_نام'}\n🆔 Telegram ID: {telegram_id}\n\nبرای تأیید یا رد پرداخت از دکمه‌های زیر استفاده کنید."
            await context.bot.send_photo(chat_id=owner_id, photo=photo.file_id, caption=owner_caption, reply_markup=payment_review_keyboard(tenant_id, payment.id))
        except Exception:
            await db.rollback()
            await update.message.reply_text("❌ ثبت رسید انجام نشد. لطفاً دوباره رسید را ارسال کنید.")


async def _payment_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":")
    if len(parts) != 4 or parts[0] != "payment" or parts[1] not in {"approve", "reject"}:
        return
    tenant_id = int(parts[2])
    payment_id = int(parts[3])
    if tenant_id != int(context.application.bot_data["tenant_id"]):
        await query.answer("⛔ این پرداخت متعلق به این Bot نیست.", show_alert=True)
        return

    async with SessionLocal() as db:
        try:
            payment = await verify_manual_payment(db, tenant_id=tenant_id, payment_id=payment_id, actor_telegram_id=query.from_user.id, approve=parts[1] == "approve")
            customer = await payment_customer(db, tenant_id=tenant_id, payment_id=payment_id)
            if parts[1] == "approve":
                service = await fulfill_verified_payment(db, tenant_id=tenant_id, payment_id=payment_id)
                order = await db.scalar(select(Order).where(Order.id == payment.order_id, Order.tenant_id == tenant_id))
                await db.commit()
                subscription_url = service.metadata_json.get("subscription_url")
                await query.edit_message_caption(caption=f"✅ پرداخت #{payment_id} تأیید شد.\n\nسرویس ساخته و لینک اشتراک صادر شد.")
                if customer and subscription_url:
                    await context.bot.send_message(customer.telegram_id, f"🎉 پرداخت شما تأیید شد و سرویس فعال شد.\n\n🧾 سفارش: #{order.id if order else payment.order_id}\n\n🔗 لینک اشتراک:\n{subscription_url}", disable_web_page_preview=True)
            else:
                await db.commit()
                await query.edit_message_caption(caption=f"❌ پرداخت #{payment_id} رد شد.\n\nمشتری باید با پشتیبانی یا ادمین پیگیری کند.")
                if customer:
                    await context.bot.send_message(customer.telegram_id, f"❌ پرداخت سفارش #{payment.order_id} تأیید نشد.\n\nلطفاً با پشتیبانی تماس بگیرید.")
            await query.answer("انجام شد")
        except PermissionError:
            await db.rollback()
            await query.answer("⛔ فقط ادمین Tenant مجاز است.", show_alert=True)
        except Exception:
            await db.rollback()
            await query.answer("❌ عملیات انجام نشد.", show_alert=True)


def build_tenant_application(*, token: str, tenant_id: int, bot_instance_id: int) -> Application:
    contract = TenantBotContract(tenant_id=int(tenant_id), bot_instance_id=int(bot_instance_id), mini_app_enabled=True)
    contract.validate()
    application = Application.builder().token(token).build()
    application.bot_data["tenant_id"] = int(tenant_id)
    application.bot_data["bot_instance_id"] = int(bot_instance_id)
    application.add_handler(CommandHandler("start", _tenant_start))
    application.add_handler(CallbackQueryHandler(_payment_review_callback, pattern=r"^payment:(approve|reject):\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(_purchase_callback, pattern=r"^(tenant:purchase|purchase:.*)$"))
    application.add_handler(MessageHandler(filters.PHOTO, _payment_receipt))
    return application


def build_tenant_contract(tenant_id: int, bot_instance_id: int) -> TenantBotContract:
    contract = TenantBotContract(tenant_id=tenant_id, bot_instance_id=bot_instance_id, mini_app_enabled=True)
    contract.validate()
    return contract


__all__: Final = [
    "TenantBotSection", "TenantAdminSection", "TenantBotContract", "TenantIsolationViolation", "assert_tenant_access", "user_menu", "admin_menu", "build_tenant_application", "build_tenant_contract"
]
