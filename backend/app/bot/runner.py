import logging

from app.bot.central import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger("3xshop.telegram")


def main():
    app = build_application()

    log.info("3XSHOP Central Bot starting")

    app.run_polling(
        allowed_updates=[
            "message",
            "callback_query",
        ],
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
