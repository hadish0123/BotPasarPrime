import asyncio
import os

import httpx

# Load root .env
try:
    from dotenv import load_dotenv
    load_dotenv("/root/3XSHOP/.env")
except Exception:  # noqa: BLE001
    pass

TOKEN = os.getenv("CENTRAL_BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()

if not TOKEN:
    raise SystemExit("CENTRAL_BOT_TOKEN is empty")

API = f"https://api.telegram.org/bot{TOKEN}"


async def tg(method, **data):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API}/{method}", json=data)
        r.raise_for_status()
        result = r.json()
        if not result.get("ok"):
            raise RuntimeError(result)
        return result["result"]


def menu():
    return {
        "keyboard": [
            [{"text": "نمایندگان PRIMEVPN"}, {"text": "پنل خودشون"}],
            [{"text": "وضعیت درخواست"}, {"text": "پشتیبانی"}],
            [{"text": "راهنما"}],
        ],
        "resize_keyboard": True
    }


async def send(chat_id, text):
    return await tg(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        reply_markup=menu()
    )


async def handle(update):
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    text = (message.get("text") or "").strip()

    chat_id = chat.get("id")
    user_id = user.get("id")

    if not chat_id:
        return

    if text in ("/start", "شروع"):
        await send(
            chat_id,
            "👑 به 3XSHOP خوش آمدید.\n\n"
            "نوع پنل خود را انتخاب کنید:"
        )

    elif text == "نمایندگان PRIMEVPN":
        await send(
            chat_id,
            "👑 ثبت درخواست نمایندگی PRIMEVPN\n\n"
            "برای شروع اطلاعات پنل و مشخصات موردنیاز را آماده کنید.\n"
            "در مرحله بعد اطلاعات شما برای بررسی مالک ارسال می‌شود."
        )

    elif text == "پنل خودشون":
        await send(
            chat_id,
            "🖥 پنل خودشون\n\n"
            "برای اتصال پنل شخصی، اطلاعات زیر موردنیاز است:\n"
            "• API Token\n"
            "• Login URL\n"
            "• Username\n"
            "• Telegram ID\n"
            "• Bot Token\n"
            "• Brand Name\n\n"
            "هزینه فعال‌سازی: ۲۵۰٬۰۰۰ تومان\n"
            "پس از ثبت و پرداخت، درخواست برای تأیید مالک ارسال می‌شود."
        )

    elif text == "وضعیت درخواست":
        await send(
            chat_id,
            "📋 وضعیت درخواست\n\n"
            "برای مشاهده وضعیت، ابتدا درخواست خود را ثبت کنید."
        )

    elif text == "پشتیبانی":
        await send(
            chat_id,
            "🎧 پشتیبانی\n\n"
            "پیام خود را ارسال کنید تا درخواست پشتیبانی ثبت شود."
        )

    elif text == "راهنما":
        await send(
            chat_id,
            "📚 راهنما\n\n"
            "3XSHOP برای مدیریت فروشگاه و ربات‌های مستقل نمایندگان طراحی شده است."
        )

    elif text.startswith("/id"):
        await send(chat_id, f"Telegram ID: {user_id}")

    else:
        await send(
            chat_id,
            "لطفاً یکی از گزینه‌های منو را انتخاب کنید."
        )


async def main():
    # Remove webhook so long polling works on staging server
    try:
        await tg("deleteWebhook", drop_pending_updates=False)
    except Exception as e:  # noqa: BLE001
        print("deleteWebhook:", e)

    me = await tg("getMe")
    print("BOT CONNECTED:", me.get("username"))

    offset = 0

    while True:
        try:
            updates = await tg(
                "getUpdates",
                offset=offset,
                timeout=25,
                allowed_updates=["message"]
            )

            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await handle(update)
                except Exception as e:  # noqa: BLE001
                    print("UPDATE ERROR:", repr(e))

        except Exception as e:  # noqa: BLE001
            print("POLL ERROR:", repr(e))
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
