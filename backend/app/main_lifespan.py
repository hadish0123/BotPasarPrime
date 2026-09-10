from contextlib import asynccontextmanager
import logging

from app.bot.central import build_application
from app.core.config import settings
from app.runtime_version import RUNTIME_VERSION

log = logging.getLogger("3xshop.api")


@asynccontextmanager
async def central_bot_lifespan(app):
    bot_application = None
    enabled = str(getattr(settings, "central_bot_enabled", True)).strip().lower() in {"1", "true", "yes", "on"}
    if enabled and settings.central_bot_token.strip():
        try:
            bot_application = build_application(settings.central_bot_token.strip())
            await bot_application.initialize()
            if bot_application.updater is None:
                raise RuntimeError("telegram_updater_unavailable")
            await bot_application.updater.start_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=False)
            await bot_application.start()
            log.info("CENTRAL BOT POLLING STARTED | runtime=%s", RUNTIME_VERSION)
        except Exception:
            log.exception("CENTRAL BOT START FAILED")
            if bot_application is not None:
                try:
                    if bot_application.updater is not None:
                        await bot_application.updater.stop()
                except Exception:
                    log.exception("CENTRAL BOT UPDATER CLEANUP FAILED")
                try:
                    await bot_application.shutdown()
                except Exception:
                    log.exception("CENTRAL BOT SHUTDOWN CLEANUP FAILED")
                bot_application = None
    elif enabled:
        log.error("CENTRAL_BOT_ENABLED=true but CENTRAL_BOT_TOKEN is empty")
    else:
        log.warning("CENTRAL_BOT_ENABLED=false; central bot disabled")

    yield

    if bot_application is not None:
        try:
            if bot_application.updater is not None:
                await bot_application.updater.stop()
        except Exception:
            log.exception("CENTRAL BOT UPDATER STOP FAILED")
        try:
            await bot_application.stop()
        except Exception:
            log.exception("CENTRAL BOT STOP FAILED")
        try:
            await bot_application.shutdown()
        except Exception:
            log.exception("CENTRAL BOT SHUTDOWN FAILED")
        log.info("CENTRAL BOT STOPPED")
