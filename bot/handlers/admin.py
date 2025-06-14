from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from dao.user_dao import UserDAO
from config import ADMIN_IDS
import pandas as pd
import os
import logging
import asyncio
from datetime import datetime

router = Router()
user_dao = UserDAO()
logger = logging.getLogger(__name__)

async def _delete_old_messages(message: Message, state: FSMContext):
    data = await state.get_data()
    message_ids = data.get("message_ids", [])[-10:]
    welcome_message_id = data.get("welcome_message_id")
    chat_id = message.chat.id
    
    tasks = []
    for msg_id in message_ids:
        if msg_id != welcome_message_id:
            try:
                tasks.append(message.bot.delete_message(chat_id=chat_id, message_id=msg_id))
            except Exception as e:
                logger.debug(f"Failed to delete message {msg_id}: {e}")
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await state.update_data(message_ids=[])
    logger.debug(f"Deleted {len(tasks)} messages for chat {chat_id}")

@router.message(Command("admin_export"))
async def cmd_admin_export(message: Message, state: FSMContext):
    if str(message.from_user.id) not in ADMIN_IDS.split(","):
        bot_message = await message.answer("У вас нет прав для этой команды.")
        await state.update_data(message_ids=[bot_message.message_id])
        logger.warning(f"Unauthorized access to /admin_export by user {message.from_user.id}")
        return

    await _delete_old_messages(message, state)
    
    try:
        users = user_dao.get_all_users()
        if not users:
            bot_message = await message.answer("Нет зарегистрированных пользователей.")
            await state.update_data(message_ids=[bot_message.message_id])
            return

        data = [{
            'ФИО': f"{user.last_name} {user.first_name} {user.patronymic or ''}".strip(),
            'Ссылка на переписку': f"https://t.me/@{message.bot.get_me().username}?start={user.telegram_id}",
            'Дата оплаты': user.last_payment_date.strftime("%d.%m.%Y") if user.last_payment_date else "Нет",
            'Сумма оплаты': user.contribution
        } for user in users]
        
        df = pd.DataFrame(data)
        excel_path = os.path.join(os.path.dirname(__file__), '..', 'users_export.xlsx')
        df.to_excel(excel_path, index=False)
        
        with open(excel_path, 'rb') as file:
            bot_message = await message.answer_document(document=file, caption="Список пользователей")
        await state.update_data(message_ids=[bot_message.message_id])
        logger.info(f"Exported {len(users)} users to Excel for admin {message.from_user.id}")
        
        os.remove(excel_path)  # Удаляем файл после отправки
    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        bot_message = await message.answer("Ошибка при экспорте. Попробуйте позже.")
        await state.update_data(message_ids=[bot_message.message_id])
