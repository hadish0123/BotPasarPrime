from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes


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


def assert_tenant_access(
    contract: TenantBotContract,
    requested_tenant_id: int,
) -> None:
    contract.validate()

    if requested_tenant_id != contract.tenant_id:
        raise TenantIsolationViolation("Cross-tenant access blocked")


def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛍️ فروشگاه",
                    callback_data=TenantBotSection.STORE.value,
                ),
                InlineKeyboardButton(
                    "📦 پلن‌ها",
                    callback_data=TenantBotSection.PLANS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛒 خرید",
                    callback_data=TenantBotSection.PURCHASE.value,
                ),
                InlineKeyboardButton(
                    "💳 پرداخت",
                    callback_data=TenantBotSection.PAYMENTS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "💰 کیف پول",
                    callback_data=TenantBotSection.WALLET.value,
                ),
                InlineKeyboardButton(
                    "📋 سفارش‌های من",
                    callback_data=TenantBotSection.MY_ORDERS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🖥️ سرویس‌های من",
                    callback_data=TenantBotSection.MY_SERVICES.value,
                ),
                InlineKeyboardButton(
                    "🔄 تمدید",
                    callback_data=TenantBotSection.RENEW.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏰ اعلان انقضا",
                    callback_data=TenantBotSection.EXPIRY.value,
                ),
                InlineKeyboardButton(
                    "🎟️ کد تخفیف",
                    callback_data=TenantBotSection.COUPON.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎁 دعوت دوستان",
                    callback_data=TenantBotSection.REFERRAL.value,
                ),
                InlineKeyboardButton(
                    "💬 پشتیبانی",
                    callback_data=TenantBotSection.SUPPORT.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ FAQ",
                    callback_data=TenantBotSection.FAQ.value,
                ),
                InlineKeyboardButton(
                    "🚀 باز کردن Mini App",
                    callback_data=TenantBotSection.MINI_APP.value,
                ),
            ],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 داشبورد",
                    callback_data=TenantAdminSection.DASHBOARD.value,
                ),
                InlineKeyboardButton(
                    "👥 کاربران",
                    callback_data=TenantAdminSection.USERS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛍️ محصولات و پلن‌ها",
                    callback_data=TenantAdminSection.PRODUCTS.value,
                ),
                InlineKeyboardButton(
                    "📋 سفارش‌ها",
                    callback_data=TenantAdminSection.ORDERS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "💳 پرداخت‌ها",
                    callback_data=TenantAdminSection.PAYMENTS.value,
                ),
                InlineKeyboardButton(
                    "💰 کیف پول",
                    callback_data=TenantAdminSection.WALLET.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎟️ کوپن",
                    callback_data=TenantAdminSection.COUPONS.value,
                ),
                InlineKeyboardButton(
                    "🎁 Referral",
                    callback_data=TenantAdminSection.REFERRAL.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🖥️ سرویس‌ها",
                    callback_data=TenantAdminSection.SERVICES.value,
                ),
                InlineKeyboardButton(
                    "📈 گزارش‌ها",
                    callback_data=TenantAdminSection.REPORTS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "📢 پیام همگانی",
                    callback_data=TenantAdminSection.BROADCAST.value,
                ),
                InlineKeyboardButton(
                    "🎫 تیکت‌ها",
                    callback_data=TenantAdminSection.TICKETS.value,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎨 تنظیمات برند",
                    callback_data=TenantAdminSection.BRANDING.value,
                ),
                InlineKeyboardButton(
                    "👑 مدیران و سطح دسترسی",
                    callback_data=TenantAdminSection.ADMINS.value,
                ),
            ],
        ]
    )


async def _tenant_start(
    update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message:
        await update.message.reply_text(
            "👋 خوش آمدید.\n\nاز منوی زیر سرویس موردنظر خود را انتخاب کنید.",
            reply_markup=user_menu(),
        )


def build_tenant_application(
    *,
    token: str,
    tenant_id: int,
    bot_instance_id: int,
) -> Application:
    contract = TenantBotContract(
        tenant_id=int(tenant_id),
        bot_instance_id=int(bot_instance_id),
        mini_app_enabled=True,
    )
    contract.validate()

    application = Application.builder().token(token).build()

    application.add_handler(
        CommandHandler(
            "start",
            _tenant_start,
        )
    )

    return application


def build_tenant_contract(
    tenant_id: int,
    bot_instance_id: int,
) -> TenantBotContract:
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
