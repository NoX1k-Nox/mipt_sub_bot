import logging
from aiohttp import web

logger = logging.getLogger(__name__)

async def handle_yookassa_webhook(request):
    # Реализуй логику обработки уведомлений YooKassa в handlers/payments.py
    logger.info("Received YooKassa webhook")
    return web.Response(text="OK")
