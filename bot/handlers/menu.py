from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from dao.user_dao import UserDAO
from bot.keyboards.inline import get_welcome_keyboard
from config import SUPPORT_URL, DOGOVOR_URL
import logging
import asyncio
from datetime import datetime

router = Router()
user_dao = UserDAO()
logger = logging.getLogger(__name__)

async def _delete_old_messages(message: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    message_ids = data.get("message_ids", [])[-10:]
    welcome_message_id = data.get("welcome_message_id")
    if isinstance(message, Message):
        chat_id = message.chat.id
    else:  # CallbackQuery
        if message.message is None:
            logger.warning(f"No message object in CallbackQuery for user {message.from_user.id}")
            return
        chat_id = message.message.chat.id
    
    tasks = []
    for msg_id in message_ids:
        if msg_id != welcome_message_id:  # Не удаляем приветствие
            try:
                tasks.append(message.bot.delete_message(chat_id=chat_id, message_id=msg_id))
            except Exception as e:
                logger.debug(f"Failed to delete message {msg_id}: {e}")
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await state.update_data(message_ids=[])
    logger.debug(f"Deleted {len(tasks)} messages for chat {chat_id}")

@router.callback_query(lambda c: c.data in ["status_associate", "status_partner"])
async def process_status(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Processing status selection for user {callback.from_user.id}")
    start_time = datetime.now()
    await _delete_old_messages(callback, state)
    
    user_data = await state.get_data()
    if not all(key in user_data for key in ["last_name", "first_name", "patronymic"]):
        bot_message = await callback.message.answer(
            "Ошибка: данные регистрации отсутствуют. Начните с /start.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        await state.clear()
        await callback.answer()
        logger.debug(f"process_status took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return

    status = "Ассоциированный партнер" if callback.data == "status_associate" else "Партнер"
    contribution = 50000 if callback.data == "status_associate" else 500000
    try:
        success = user_dao.create_user(
            telegram_id=callback.from_user.id,
            last_name=user_data["last_name"],
            first_name=user_data["first_name"],
            patronymic=user_data["patronymic"],
            status=status,
            contribution=contribution,
            username=callback.from_user.username
        )
        if success:
            # Удаляем сообщение о выборе статуса
            try:
                welcome_message_id = user_data.get("welcome_message_id")
                if welcome_message_id:
                    await callback.message.bot.delete_message(
                        chat_id=callback.message.chat.id,
                        message_id=welcome_message_id
                    )
            except Exception as e:
                logger.debug(f"Failed to delete status selection message: {e}")

            user = user_dao.get_user(callback.from_user.id)
            status_text = f"{user.status} | {user.contribution} руб."
            bot_message = await callback.message.answer(
                # f"{user.first_name} {user.patronymic or ''}, добро пожаловать в бот Физтех-Союза 💎\n\n"
                # f"Он поможет вам официально закрепить вступление и настроить автоматическую оплату ежегодного членского взноса.\n\n"
                f"Ваш статус: {status_text}\n\n"
                f"[Договор пожертвований]({DOGOVOR_URL})",
                reply_markup=get_welcome_keyboard(),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        else:
            bot_message = await callback.message.answer(
                "Ошибка регистрации. Попробуйте снова с /start_name.",
                reply_markup=get_welcome_keyboard()
            )
            await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        await state.clear()
    except Exception as e:
        logger.error(f"Error in process_status for user {callback.from_user.id}: {e}")
        bot_message = await callback.message.answer(
            f"Произошла ошибка: {e}. Попробуйте снова с /start_name.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        await state.clear()
    await callback.answer()
    logger.debug(f"process_status took {(datetime.now() - start_time).total_seconds():.2f} seconds")
