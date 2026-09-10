from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import logging

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.core.db import SessionLocal
from app.models.entities import Coupon, CouponUsage, Order, OrderItem, Referral, ReferralTransaction, Service, TenantSettings, User
from app.services.coupons import calculate_coupon_for_order
from app.services.referrals import create_referral
from app.services.shop import create_order_from_plan
from app.services.provisioning import get_service_subscription
from app.services.wallet import get_or_create_wallet

log = logging.getLogger("primevpn.tenant-extensions")


def _home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 فروشگاه", callback_data="tenant:store")],
        [InlineKeyboardButton("🖥 سرویس‌های من", callback_data="ext:services")],
        [InlineKeyboardButton("📦 سفارش‌های من", callback_data="ext:orders")],
        [InlineKeyboardButton("💳 پرداخت‌های من", callback_data="tenant:payments")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="tenant:wallet")],
        [InlineKeyboardButton("🎟 کد تخفیف", callback_data="ext:coupon")],
        [InlineKeyboardButton("🤝 دعوت دوستان", callback_data="ext:referral")],
        [InlineKeyboardButton("🎫 پشتیبانی", callback_data="tenant:tickets")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="ext:help")],
    ])


def _back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ منوی اصلی", callback_data="tenant:home")]])


async def _user(db, tg):
    user = await db.scalar(select(User).where(User.telegram_id == tg.id))
    if user is None:
        user = User(telegram_id=tg.id, username=tg.username, first_name=tg.first_name)
        db.add(user)
        await db.flush()
    return user


async def _services(query, context):
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        user = await _user(db, query.from_user)
        rows = list((await db.scalars(select(Service).where(Service.tenant_id == tenant_id, Service.user_id == user.id).order_by(Service.id.desc()).limit(30))).all())
    buttons = []
    text = "🖥 سرویس‌های من\n\n"
    for s in rows:
        exp = s.expires_at.strftime("%Y-%m-%d %H:%M") if s.expires_at else "—"
        text += f"#{s.id} | {s.status} | {exp}\n"
        buttons.append([InlineKeyboardButton(f"🔐 مشاهده سرویس #{s.id}", callback_data=f"ext:service:{s.id}")])
    buttons.append([InlineKeyboardButton("⬅️ منوی اصلی", callback_data="tenant:home")])
    await query.edit_message_text(text if rows else "🖥 هنوز سرویسی ندارید.", reply_markup=InlineKeyboardMarkup(buttons))


async def _service(query, context, service_id: int):
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        user = await _user(db, query.from_user)
        service = await db.scalar(select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id, Service.user_id == user.id))
        if service is None:
            raise ValueError("service_not_found")
        remote = {}
        try:
            value = await get_service_subscription(db, tenant_id=tenant_id, service_id=service.id)
            if isinstance(value, dict):
                remote = value
        except Exception:
            log.exception("failed to load service subscription tenant=%s service=%s", tenant_id, service_id)
    link = remote.get("subscription_url") or remote.get("subscription") or remote.get("link") or remote.get("config")
    text = f"🔐 سرویس #{service.id}\n\n🆔 {service.external_id or 'در حال ساخت'}\n📌 وضعیت: {service.status}\n⏳ انقضا: {service.expires_at:%Y-%m-%d %H:%M UTC if service.expires_at else '—'}"
    if link:
        text += f"\n\n📎 لینک اشتراک/کانفیگ:\n{link}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تمدید", callback_data=f"renew:{service.id}")],
        [InlineKeyboardButton("⬅️ سرویس‌های من", callback_data="ext:services")],
    ]))


async def _orders(query, context):
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        user = await _user(db, query.from_user)
        rows = list((await db.execute(select(Order, OrderItem).outerjoin(OrderItem, OrderItem.order_id == Order.id).where(Order.tenant_id == tenant_id, Order.user_id == user.id).order_by(Order.id.desc()).limit(30))).all())
    text = "📦 سفارش‌های من\n\n"
    for order, item in rows:
        name = item.snapshot_plan_name if item else "—"
        text += f"#{order.id} | {name} | {order.total:,.0f} تومان | {order.status}\n"
    await query.edit_message_text(text if rows else "📦 هنوز سفارشی ثبت نکرده‌اید.", reply_markup=_back())


async def _referral(query, context):
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        user = await _user(db, query.from_user)
        referral = await db.scalar(select(Referral).where(Referral.tenant_id == tenant_id, Referral.inviter_user_id == user.id).order_by(Referral.id.desc()))
        settings_row = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
        percent = (settings_row.settings or {}).get("referral_percent", "0") if settings_row else "0"
        wallet = await get_or_create_wallet(db, tenant_id, user.id)
        earned = await db.scalar(select(func.coalesce(func.sum(ReferralTransaction.amount), 0)).where(ReferralTransaction.tenant_id == tenant_id, ReferralTransaction.user_id == user.id, ReferralTransaction.ledger_type == "commission")) or 0
        if referral is None:
            # A reusable inviter code is represented by a referral row only after a real invite.
            code = f"PRIME{tenant_id}-{user.id}".upper()
            try:
                referral = await create_referral(db, tenant_id, user.id, user.id + 1, code)
                await db.flush()
            except Exception:
                await db.rollback()
                referral = None
        await db.commit()
    code = referral.code if referral else f"PRIME{tenant_id}-{user.id}".upper()
    text = f"🤝 دعوت دوستان\n\nکد دعوت شما: {code}\nدرصد کمیسیون فعلی: {percent}%\nدرآمد دعوت: {Decimal(str(earned)):,.0f} تومان\nموجودی کیف پول: {Decimal(str(wallet.balance)):,.0f} تومان\n\nلینک دعوت را می‌توانید به دوستانتان بدهید و از آنها بخواهید کد را هنگام ثبت‌نام/خرید وارد کنند."
    await query.edit_message_text(text, reply_markup=_back())


async def _coupon_prompt(query, context):
    context.user_data["ext_action"] = "coupon"
    await query.edit_message_text("🎟 کد تخفیف را ارسال کنید.\n\nبرای لغو /cancel", reply_markup=_back())


async def _coupon_check(update, context, code: str):
    tenant_id = int(context.bot_data["tenant_id"])
    async with SessionLocal() as db:
        # Validate against a representative-friendly example subtotal: the user gets the exact
        # discount once a plan is selected. This call intentionally does not consume the coupon.
        plans = list((await db.execute(select(OrderItem.snapshot_price).where(OrderItem.order_id.in_(select(Order.id).where(Order.tenant_id == tenant_id)).limit(1))).all())
        sample = Decimal(str(plans[0][0])) if plans and plans[0][0] is not None else Decimal("0")
        try:
            coupon, discount = await calculate_coupon_for_order(db, tenant_id, code, sample)
            result = f"✅ کد {coupon.code} معتبر است.\nتخفیف محاسبه‌شده روی مبلغ نمونه: {discount:,.0f} تومان"
            context.user_data["coupon_code"] = coupon.code
        except ValueError as exc:
            result = f"❌ کد تخفیف معتبر نیست: {exc}"
    context.user_data.pop("ext_action", None)
    await update.message.reply_text(result, reply_markup=_home())


async def _help(query):
    await query.edit_message_text(
        "ℹ️ راهنمای PRIMEVPN\n\n"
        "🛒 از فروشگاه پلن را انتخاب کنید.\n"
        "💳 پرداخت مستقیم با کارت انجام می‌شود و مدیر نماینده رسید را تأیید می‌کند.\n"
        "💰 کیف پول برای خرید و تمدید استفاده می‌شود.\n"
        "🖥 از سرویس‌های من می‌توانید لینک اشتراک و وضعیت انقضا را ببینید.\n"
        "🎟 کد تخفیف قبل از خرید قابل بررسی است.\n"
        "🤝 از دعوت دوستان برای معرفی PRIMEVPN استفاده کنید.\n"
        "🎫 هر مشکل را از تیکت پشتیبانی ارسال کنید.",
        reply_markup=_back(),
    )


async def _command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    await update.message.reply_text("🏠 PRIMEVPN\n\nاز منوی زیر انتخاب کنید:", reply_markup=_home())


async def _callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    data = query.data or ""
    if not data.startswith("ext:"):
        return
    await query.answer()
    try:
        if data == "ext:services":
            await _services(query, context)
        elif data.startswith("ext:service:"):
            await _service(query, context, int(data.rsplit(":", 1)[1]))
        elif data == "ext:orders":
            await _orders(query, context)
        elif data == "ext:referral":
            await _referral(query, context)
        elif data == "ext:coupon":
            await _coupon_prompt(query, context)
        elif data == "ext:help":
            await _help(query)
    except Exception as exc:
        log.exception("tenant extension callback failed tenant=%s data=%s", context.bot_data.get("tenant_id"), data)
        await query.answer(str(exc)[:190], show_alert=True)


async def _message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    action = context.user_data.get("ext_action")
    if action == "coupon":
        text = (update.message.text or "").strip()
        if text == "/cancel":
            context.user_data.pop("ext_action", None)
            await update.message.reply_text("لغو شد.", reply_markup=_home())
            return
        await _coupon_check(update, context, text)


def install_tenant_extensions(application) -> None:
    # Negative group runs before the legacy tenant handlers, allowing these new UX sections
    # to coexist without changing the existing production purchase/payment flow.
    application.add_handler(CommandHandler("menu", _command), group=-1)
    application.add_handler(CommandHandler("orders", _command), group=-1)
    application.add_handler(CommandHandler("wallet", _command), group=-1)
    application.add_handler(CommandHandler("services", _command), group=-1)
    application.add_handler(CommandHandler("referral", _command), group=-1)
    application.add_handler(CommandHandler("coupon", _command), group=-1)
    application.add_handler(CommandHandler("help", _command), group=-1)
    application.add_handler(CallbackQueryHandler(_callback, pattern=r"^ext:"), group=-1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _message), group=-1)
