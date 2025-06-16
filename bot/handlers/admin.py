from aiogram import Router
from aiogram.types import Message, FSInputFile
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

@router.message(Command(commands=["users"]))
async def export_users(message: Message, state: FSMContext):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("Доступ запрещён.")
        return
    logger.info(f"Export requested by admin {message.from_user.id}")
    await _delete_old_messages(message, state)
    try:
        users = user_dao.get_all_users()

        data = []
        for user in users:
            full_name = f"{user.last_name} {user.first_name} {user.patronymic or ''}".strip()
            chat_link = (
                f"https://t.me/{user.username}"
                if hasattr(user, "username") and user.username
                else f"ID: {user.telegram_id}"
            )
            payment_date = user.last_payment_date.strftime("%Y-%m-%d %H:%M") if user.last_payment_date else ""
            payment_amount = user.contribution if user.contribution is not None else ""

            data.append({
                "ФИО": full_name,
                "Ссылка на переписку": chat_link,
                "Дата оплаты": payment_date,
                "Сумма оплаты": payment_amount
            })

        df = pd.DataFrame(data)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_file = f"users_export_{timestamp}.xlsx"
        df.to_excel(excel_file, index=False)

        bot_message = await message.answer_document(
            document=FSInputFile(excel_file),
            caption="Выгрузка пользователей"
        )
        os.remove(excel_file)
        await state.update_data(message_ids=[bot_message.message_id])
        logger.info(f"Exported {len(users)} users to Excel")

    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        bot_message = await message.answer(f"Ошибка выгрузки: {e}")
        await state.update_data(message_ids=[bot_message.message_id])
