from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from dao.user_dao import UserDAO
from bot.keyboards.inline import get_registration_keyboard
from bot.states import RegistrationStates
from config import DOGOVOR_URL
import logging
import asyncio

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

@router.message(RegistrationStates.waiting_for_fio)
async def process_fio(message: Message, state: FSMContext):
    logger.info(f"Processing FIO for user {message.from_user.id}")
    await _delete_old_messages(message, state)
    fio = message.text.strip().split()
    if len(fio) < 2:
        bot_message = await message.answer(
            "Пожалуйста, введите как минимум фамилию и имя, например: Иванов Иван или Иванов Иван Иванович"
        )
        await state.update_data(message_ids=[message.message_id, bot_message.message_id])
        return

    last_name = fio[0]
    first_name = fio[1]
    patronymic = fio[2] if len(fio) > 2 else None

    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        data = await state.get_data()
        welcome_message_id = data.get("welcome_message_id")
        await message.bot.delete_message(chat_id=message.chat.id, message_id=welcome_message_id)
    except Exception as e:
        logger.debug(f"Failed to delete FIO or welcome message: {e}")

    await state.update_data(last_name=last_name, first_name=first_name, patronymic=patronymic)
    bot_message = await message.answer(
        "Чтобы завершить вступление, необходимо настроить автоматическую оплату ежегодного членского взноса.\n\n"
        "Пожалуйста, выберите статус для оплаты ниже.\n\n",
        reply_markup=get_registration_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
    logger.info(f"Stored FIO and sent status selection to user {message.from_user.id}")