from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORT_URL, NEWS_CHAT_URL, PARTNERS_CHAT_URL, MEMBERS_CHAT_URL

def get_welcome_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти к оплате", callback_data="pay")],
        [InlineKeyboardButton(text="Служба поддержки", url=SUPPORT_URL)]
    ])

def get_registration_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ассоциированный партнер | 50 000 руб.", callback_data="status_associate")],
        [InlineKeyboardButton(text="Партнер | 500 000 руб.", callback_data="status_partner")]
    ])

def get_newbie_success_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вступить в чат", url=SUPPORT_URL)]
    ])

def get_member_success_keyboard_fir():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вступить в чат партнеров", url=PARTNERS_CHAT_URL)],
    ])

def get_member_success_keyboard_sec():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Физтех-Союз | Новости", url=NEWS_CHAT_URL)],
        [InlineKeyboardButton(text="Вступить в чат участников Физтех-Союза", url=MEMBERS_CHAT_URL)]
    ])

def get_reminder_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Служба поддержки", url=SUPPORT_URL)]
    ])

def get_admin_nonpayment_keyboard(telegram_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Связаться", url=f"https://t.me/{telegram_id}")]
    ])