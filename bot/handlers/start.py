from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline import get_welcome_keyboard, get_member_success_keyboard_fir, get_member_success_keyboard_sec
from bot.states import RegistrationStates
from dao.user_dao import UserDAO
from dao.payment_dao import PaymentDAO
from config import DOGOVOR_URL
import logging
import asyncio
from datetime import datetime
from yookassa import Payment

router = Router()
user_dao = UserDAO()
payment_dao = PaymentDAO()
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

@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: Message, state: FSMContext):
    await _delete_old_messages(message, state)
    deep_link = message.text.split(" ")[1] if len(message.text.split(" ")) > 1 else ""
    if deep_link.startswith("payment_success_"):
        payment_id = deep_link.replace("payment_success_", "")
        logger.info(f"Checking payment via deep-link for user {message.from_user.id}: {payment_id}")
        user = user_dao.get_user(message.from_user.id)
        if not user:
            bot_message = await message.answer(
                "Ошибка: пользователь не зарегистрирован. Начните с /start.",
                reply_markup=get_welcome_keyboard()
            )
            await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
            await state.clear()
            return
        try:
            yookassa_id = payment_dao.get_yookassa_id(payment_id)
            if not yookassa_id:
                bot_message = await message.answer(
                    "Платёж не найден. Попробуйте позже или используйте /check_payment.",
                    reply_markup=get_welcome_keyboard()
                )
                await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
                return
            payment = Payment.find_one(yookassa_id)
            if payment.status == "succeeded":
                payment_method_id = payment.payment_method.id if payment.payment_method else None
                user_dao.update_payment(
                    telegram_id=user.telegram_id,
                    last_payment_date=datetime.now().date(),
                    contribution=user.contribution,
                    status=user.status,
                    payment_method_id=payment_method_id
                )
                bot_message = await message.answer(
                    "Успешно ✅\nБыть Физтехом — это навсегда!\n\nДобавляйтесь в наш чат ассоциированных партнёров.",
                    reply_markup=get_member_success_keyboard_fir()
                )
                await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
                await asyncio.sleep(3)
                second_message = await message.answer(
                    "А чтобы быть в курсе новостей, инициатив и событий —\n"
                    "обязательно подпишитесь на Telegram-канал «Физтех-Союз.Новости»\n\n"
                    "При желании еще можете вступить в большой чат всех участников Физтех-Союза "
                    "(включая владельцев карты Тинькофф-Физтех-Союз).",
                    reply_markup=get_member_success_keyboard_sec()
                )
                await state.update_data(
                    message_ids=[bot_message.message_id, second_message.message_id],
                    welcome_message_id=bot_message.message_id,
                    payment_id=None
                )
                logger.info(f"Payment {payment_id} confirmed via deep-link for user {message.from_user.id}")
            else:
                bot_message = await message.answer(
                    f"Платёж ещё не подтверждён. Статус: {payment.status}. Попробуйте позже.",
                    reply_markup=get_welcome_keyboard()
                )
                await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        except Exception as e:
            logger.error(f"Error checking payment via deep-link for user {message.from_user.id}: {e}")
            bot_message = await message.answer(
                "Ошибка при проверке платежа. Попробуйте позже или используйте /check_payment.",
                reply_markup=get_welcome_keyboard()
            )
            await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
    else:
        await cmd_start(message, state)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    logger.info(f"Processing /start for user {message.from_user.id}")
    user = user_dao.get_user(message.from_user.id)
    await _delete_old_messages(message, state)
    await state.clear()
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete /start message: {e}")

    if user:
        status_text = f"{user.status} | {user.contribution} руб."
        bot_message = await message.answer(
            f"{user.first_name} {user.patronymic or ''}, добро пожаловать в бот Физтех-Союза 💙\n\n"
            f"Он поможет вам официально закрепить вступление и настроить автоматическую оплату ежегодного членского взноса.\n\n"
            f"Ваш статус: {status_text}\n\n"
            f"[Договор пожертвований]({DOGOVOR_URL})",
            reply_markup=get_welcome_keyboard(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        logger.info(f"Sent welcome message to user {message.from_user.id}")
    else:
        bot_message = await message.answer(
            "Добро пожаловать в бот Физтех-Союза 💙\n\nНапишите, пожалуйста, свои ФИО:"
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        await state.set_state(RegistrationStates.waiting_for_fio)
        logger.info(f"Started registration for user {message.from_user.id}")
