from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import logging

logger = logging.getLogger(__name__)

class UpdateFilterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Получаем update_id из data, если он нужен
        update = data.get("raw_update")  # В aiogram 3.x raw_update содержит объект Update
        update_id = update.update_id if update else None
        
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            logger.debug(f"Processing update {update_id} from user {user_id}")
            return await handler(event, data)
        else:
            logger.warning(f"Unsupported event type: {type(event)}")
            return