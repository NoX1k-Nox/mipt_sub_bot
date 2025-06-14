import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from bot.handlers.start import router as start_router
from bot.handlers.registration import router as registration_router
from bot.handlers.menu import router as menu_router
from bot.handlers.payments import router as payments_router
from bot.handlers.admin import router as admin_router
from bot.middlewares.update_filter import UpdateFilterMiddleware
from config import BOT_TOKEN
from scheduler import setup_scheduler
import asyncio
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

main_router = Router()

main_router.include_router(start_router)
main_router.include_router(registration_router)
main_router.include_router(menu_router)
main_router.include_router(payments_router)
main_router.include_router(admin_router)

async def on_startup(dp):
    logger.info("Starting bot...")
    dp.message.outer_middleware(UpdateFilterMiddleware())
    dp.callback_query.outer_middleware(UpdateFilterMiddleware())
    logger.info("Routers and middleware included")
    setup_scheduler()

async def on_shutdown(app):
    logger.info("Shutting down...")
    for ws in app.get("websockets", []):
        await ws.close()
    if "bot" in app:
        await app["bot"].session.close()
        logger.info("Bot session closed")
    await app.shutdown()
    await app.cleanup()

async def handle_webhook(request):
    logger.info(f"Received webhook request: {await request.text()}")
    dp = request.app["dp"]
    bot = request.app["bot"]
    try:
        update = await request.json()
        await dp.feed_webhook_update(bot=bot, update=update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return web.Response(text="OK")

async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(main_router)
    await on_startup(dp)

    webhook_path = f"/{BOT_TOKEN}"
    webhook_url = f"https://0f46-185-223-93-139.ngrok-free.app{webhook_path}"
    try:
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app.router.add_post(webhook_path, handle_webhook)
    app.router.add_post("/yookassa", payments_router.webhook_handler)
    app.on_shutdown.append(on_shutdown)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "0.0.0.0", 8443)
        await site.start()
        logger.info("Web server started on port 8443")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        return

    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
