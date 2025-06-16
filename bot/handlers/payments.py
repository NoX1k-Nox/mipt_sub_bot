from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from yookassa import Configuration, Payment
from dao.user_dao import UserDAO
from dao.payment_dao import PaymentDAO
from bot.keyboards.inline import get_member_success_keyboard_fir, get_member_success_keyboard_sec, get_welcome_keyboard, get_reminder_keyboard
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, BOT_USERNAME
import logging
import uuid
import asyncio
from datetime import datetime
from aiohttp import web

router = Router()
user_dao = UserDAO()
payment_dao = PaymentDAO()
logger = logging.getLogger(__name__)

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

async def _delete_old_messages(message: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    message_ids = data.get("message_ids", [])[-10:]
    welcome_message_id = data.get("welcome_message_id")
    if isinstance(message, Message):
        chat_id = message.chat.id
    else:
        if message.message is None:
            logger.warning(f"No message object in CallbackQuery for user {message.from_user.id}")
            return
        chat_id = message.message.chat.id

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

async def webhook_handler(request):
    logger.info(f"Received YooKassa webhook: {await request.text()}")
    try:
        data = await request.json()
        if data["event"] == "payment.succeeded":
            yookassa_id = data["object"]["id"]
            payment_id = data["object"]["metadata"]["payment_id"]
            telegram_id = data["object"]["metadata"]["telegram_id"]
            payment_method_id = data["object"]["payment_method"]["id"] if data["object"]["payment_method"] else None
            amount = float(data["object"]["amount"]["value"])
            payment_dao.update_payment_status(yookassa_id, "succeeded")
            user = user_dao.get_user(int(telegram_id))
            if user:
                is_first_payment = user.last_payment_date is None
                user_dao.update_payment(
                    telegram_id=int(telegram_id),
                    last_payment_date=datetime.now().date(),
                    contribution=user.contribution,
                    status=user.status,
                    payment_method_id=payment_method_id
                )
                if is_first_payment:
                    bot = request.app["bot"]
                    bot_message = await bot.send_message(
                        chat_id=telegram_id,
                        text="Успешно ✅\nБыть Физтехом — это навсегда!\n\nДобавляйтесь в наш чат ассоциированных партнёров.",
                        reply_markup=get_member_success_keyboard_fir()
                    )
                    await asyncio.sleep(5)
                    await bot.send_message(
                        chat_id=telegram_id,
                        text="А чтобы быть в курсе новостей, инициатив и событий —\n"
                        "обязательно подпишитесь на Telegram-канал <b>«Физтех-Союз.Новости»</b>\n\n"
                        "При желании еще можете вступить в большой чат всех участников Физтех-Союза "
                        "(включая владельцев карты Тинькофф-Физтех-Союз).",
                        parse_mode="html",
                        reply_markup=get_member_success_keyboard_sec()
                    )
                    logger.info(f"Payment succeeded: payment_id={payment_id}, yookassa_id={yookassa_id}, user={telegram_id}")
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Error processing YooKassa webhook: {e}")
        return web.Response(text="Error", status=500)

@router.callback_query(lambda c: c.data == "pay")
async def process_payment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.info(f"Processing payment for user {callback.from_user.id}")
    user = user_dao.get_user(callback.from_user.id)
    await _delete_old_messages(callback, state)
    if not user:
        bot_message = await callback.message.answer(
            "Ошибка: пользователь не зарегистрирован. Начните с /start.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        await callback.answer()
        return

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        logger.error("YOOKASSA_SHOP_ID or YOOKASSA_SECRET_KEY not set")
        bot_message = await callback.message.answer(
            "Платежи временно недоступны. Обратитесь в поддержку.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        await callback.answer()
        return

    payment_id = str(uuid.uuid4())
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{user.contribution}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{BOT_USERNAME}?start=payment_success_{payment_id}"
            },
            "capture": True,
            "description": f"Членский взнос: {user.status}",
            "metadata": {"telegram_id": str(user.telegram_id), "payment_id": payment_id},
            "save_payment_method": True
        })
        payment_dao.save_payment(payment_id, payment.id, user.telegram_id)
        confirmation_url = payment.confirmation.confirmation_url
        bot_message = await callback.message.answer(
            f"Для оплаты членского взноса ({user.contribution} руб.) перейдите по ссылке:\n{confirmation_url}\n\n",
            reply_markup=get_reminder_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id, payment_id=payment_id)
        logger.info(f"Sent payment link {payment_id} to user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error creating payment for user {callback.from_user.id}: {e}")
        bot_message = await callback.message.answer(
            "Ошибка при создании платежа. Попробуйте позже."
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
    await callback.answer()

@router.message(Command("check_payment"))
async def check_payment(message: Message, state: FSMContext):
    logger.info(f"Checking payment for user {message.from_user.id}")
    await _delete_old_messages(message, state)
    user = user_dao.get_user(message.from_user.id)
    if not user:
        bot_message = await message.answer(
            "Ошибка: пользователь не зарегистрирован. Начните с /start.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        return

    data = await state.get_data()
    payment_id = data.get("payment_id")
    if not payment_id:
        bot_message = await message.answer(
            "Нет активных платежей. Создайте новый платёж, нажав 'Перейти к оплате'.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
        return

    try:
        yookassa_id = payment_dao.get_yookassa_id(payment_id)
        if not yookassa_id:
            bot_message = await message.answer(
                "Платёж не найден. Создайте новый платёж.",
                reply_markup=get_welcome_keyboard()
            )
            await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id, payment_id=None)
            return
        payment = Payment.find_one(yookassa_id)
        if payment.status == "succeeded":
            is_first_payment = user.last_payment_date is None
            payment_method_id = payment.payment_method.id if payment.payment_method else None
            user_dao.update_payment(
                telegram_id=user.telegram_id,
                last_payment_date=datetime.now().date(),
                contribution=user.contribution,
                status=user.status,
                payment_method_id=payment_method_id
            )
            if is_first_payment:
                bot_message = await message.answer(
                    "Успешно ✅\nБыть Физтехом — это навсегда!\n\nДобавляйтесь в наш чат ассоциированных партнёров.",
                    reply_markup=get_member_success_keyboard_fir()
                )
                await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
                await asyncio.sleep(5)
                second_message = await message.answer(
                    "А чтобы быть в курсе новостей, инициатив и событий —\n"
                    "обязательно подпишитесь на Telegram-канал <b>«Физтех-Союз.Новости»</b>\n\n"
                    "При желании еще можете вступить в большой чат всех участников Физтех-Союза "
                    "(включая владельцев карты Тинькофф-Физтех-Союз).",
                    parse_mode="html",
                    reply_markup=get_member_success_keyboard_sec()
                )
                await state.update_data(
                    message_ids=[bot_message.message_id, second_message.message_id],
                    welcome_message_id=bot_message.message_id,
                    payment_id=None
                )
                logger.info(f"Payment {payment_id} confirmed for user {message.from_user.id}")
        else:
            bot_message = await message.answer(
                f"Платёж ещё не подтверждён. Статус: {payment.status}. Попробуйте позже.",
                reply_markup=get_welcome_keyboard()
            )
            await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)
    except Exception as e:
        logger.error(f"Error checking payment for user {message.from_user.id}: {e}")
        bot_message = await message.answer(
            "Ошибка при проверке платежа. Попробуйте позже или обратитесь в поддержку.",
            reply_markup=get_welcome_keyboard()
        )
        await state.update_data(message_ids=[bot_message.message_id], welcome_message_id=bot_message.message_id)

router.webhook_handler = webhook_handler
