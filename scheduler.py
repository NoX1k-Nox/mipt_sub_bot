from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dao.user_dao import UserDAO
from yookassa import Payment
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_IDS
from bot.db.database import SessionLocal
from bot.keyboards.inline import get_reminder_keyboard, get_admin_notification_button
from dao.models import User
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
user_dao = UserDAO()

bot = Bot(token=BOT_TOKEN)

RETRY_DAYS = (1, 10, 13, 14)

async def notify_user_success(user):
    try:
        await bot.send_message(
            user.telegram_id,
            "✅ Ваш ежегодный членский взнос успешно оплачен. Спасибо!",
            reply_markup=get_reminder_keyboard()
        )
        logger.info(f"!!!Success payment!!!")
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение об успешной оплате {user.telegram_id}: {e}")

async def notify_admins_about_unpaid_user(user):
    if not user.username:
        logger.info(f"Skipping admin notification for user {user.telegram_id}: no username")
        return

    message_text = (
        f"⚠️ Участник {user.last_name} {user.first_name} {user.patronymic} "
        f"не оплатил взнос в течение 14 дней.\n"
        "Рекомендуется связаться вручную и напомнить о необходимости оплаты."
    )

    # keyboard = InlineKeyboardMarkup(inline_keyboard=[
    #     [InlineKeyboardButton(text="Открыть чат", url=f"https://t.me/{user.username}")]
    # ])

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message_text, reply_markup=get_admin_notification_button(user.username))
            logger.info(f"Sending admin notification for user {user.telegram_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

async def handle_failed_payment(session, user, days_since_fail):
    user.last_failed_payment_date = datetime.now().date()
    session.commit()
    logger.info(f"Updated last_failed_payment_date for user {user.telegram_id} to {user.last_failed_payment_date}")

    if days_since_fail is None:
        next_retry = "Пожалуйста, пополните баланс карты, и мы попробуем снова через сутки."
    elif days_since_fail == 1:
        next_retry = "Пожалуйста, пополните баланс карты, и мы попробуем снова через 9 дней."
    elif days_since_fail == 10:
        next_retry = "Пожалуйста, пополните баланс карты, и мы попробуем снова через 3 дня."
    elif days_since_fail == 13:
        next_retry = "Пожалуйста, пополните баланс карты, и мы попробуем снова через сутки."
    elif days_since_fail == 14:
        logger.info(f"Day 14 for user {user.telegram_id}: skipping user notification")
        return
    else:
        return

    try:
        await bot.send_message(
            user.telegram_id,
            f"📍 Мы пытались списать членский взнос, но на карте недостаточно средств.\n\n{next_retry}",
            reply_markup=get_reminder_keyboard()
        )
        logger.info(f"Уведомление отправлено пользователю {user.telegram_id}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {user.telegram_id}: {e}")

async def check_subscriptions():
    session = SessionLocal()
    logger.info("🔄 Checking subscriptions")
    try:
        users = user_dao.get_all_users()
        logger.info(f"Retrieved {len(users)} users")

        for user in users:
            if not (user.last_payment_date and user.payment_method_id):
                logger.info(f"Skipping user {user.telegram_id}: no last_payment_date or payment_method_id")
                continue

            db_user = session.query(User).filter_by(telegram_id=user.telegram_id).first()
            if not db_user:
                logger.error(f"User {user.telegram_id} not found in database")
                continue

            last_payment = db_user.last_payment_date.date()
            today = datetime.now().date()
            deadline = last_payment + relativedelta(years=1)
            admin_notification_date = deadline + timedelta(days=14)
            pre_expiry_notification_date = deadline - timedelta(days=1)

            if today == pre_expiry_notification_date:
                if db_user.pre_expiry_notified_date != today:
                    try:
                        await bot.send_message(
                            db_user.telegram_id,
                            "⏳ Завтра будет попытка списания ежегодного членского взноса. "
                            "Пожалуйста, убедитесь, что на вашей карте достаточно средств.",
                            reply_markup=get_reminder_keyboard()
                        )
                        db_user.pre_expiry_notified_date = today
                        session.commit()
                        logger.info(f"A warning was sent to the user the day before the debit {db_user.telegram_id}")
                    except Exception as e:
                        logger.error(f"Couldn't send a warning to the user {db_user.telegram_id}: {e}")

            if today < deadline:
                logger.info(f"Skipping user {db_user.telegram_id}: subscription valid until {deadline}")
                continue

            if today >= admin_notification_date:
                if not db_user.admin_notified_date:
                    logger.info(f"Sending admin notification for user {db_user.telegram_id}")
                    await notify_admins_about_unpaid_user(db_user)
                    db_user.admin_notified_date = today
                    session.commit()
                else:
                    logger.info(f"Already notified admin about user {db_user.telegram_id}, skipping")
                continue

            if db_user.last_failed_payment_date and db_user.last_failed_payment_date.date() == today:
                logger.info(f"Skipping user {db_user.telegram_id}: already attempted today")
                continue

            days_since_fail = None
            if db_user.last_failed_payment_date:
                days_since_fail = (today - db_user.last_failed_payment_date.date()).days
                if days_since_fail not in (1, 10, 13):
                    logger.info(f"Skipping user {db_user.telegram_id}: days_since_fail={days_since_fail} not in (1, 10, 13)")
                    continue
            else:
                if today != deadline:
                    logger.info(f"Skipping user {db_user.telegram_id}: today={today} != deadline={deadline}")
                    continue

            logger.info(f"Attempting payment for user {db_user.telegram_id}")
            payment_id = str(uuid.uuid4())

            try:
                payment = Payment.create({
                    "amount": {
                        "value": f"{db_user.contribution}.00",
                        "currency": "RUB"
                    },
                    "payment_method_id": db_user.payment_method_id,
                    "capture": True,
                    "description": f"Ежегодный членский взнос: {db_user.status}",
                    "metadata": {
                        "telegram_id": str(db_user.telegram_id),
                        "payment_id": payment_id
                    }
                })

                if payment.status == "succeeded":
                    user_dao.update_payment(
                        telegram_id=db_user.telegram_id,
                        last_payment_date=datetime.now().date(),
                        contribution=db_user.contribution,
                        status=db_user.status,
                        payment_method_id=db_user.payment_method_id
                    )
                    db_user.last_failed_payment_date = None
                    session.commit()
                    logger.info(f"✅ Renewed subscription for user {db_user.telegram_id}")
                    await notify_user_success(db_user)

                else:
                    await handle_failed_payment(session, db_user, days_since_fail)

            except Exception as e:
                logger.error(f"❌ Error renewing subscription for user {db_user.telegram_id}: {e}")
                await handle_failed_payment(session, db_user, days_since_fail)

    except Exception as e:
        logger.error(f"Error checking subscriptions: {e}")
    finally:
        session.close()

def setup_scheduler():
    scheduler.add_job(
        check_subscriptions,
        # trigger=CronTrigger(hour=13, minute=0, timezone="Europe/Moscow"),
        trigger=CronTrigger(second="*/20"),
        id="check_subscriptions",
        replace_existing=True
    )
    scheduler.start()
