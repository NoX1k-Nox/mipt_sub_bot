from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dao.user_dao import UserDAO
from yookassa import Payment
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
user_dao = UserDAO()

async def check_subscriptions():
    logger.info("Checking subscriptions")
    try:
        users = user_dao.get_all_users()
        for user in users:
            if user.last_payment_date and user.payment_method_id:
                last_payment = user.last_payment_date.date()
                if datetime.now().date() >= last_payment + timedelta(days=365):
                    payment_id = str(uuid.uuid4())
                    try:
                        payment = Payment.create({
                            "amount": {
                                "value": f"{user.contribution}.00",
                                "currency": "RUB"
                            },
                            "payment_method_id": user.payment_method_id,
                            "capture": True,
                            "description": f"Ежегодный членский взнос: {user.status}",
                            "metadata": {"telegram_id": str(user.telegram_id), "payment_id": payment_id}
                        })
                        if payment.status == "succeeded":
                            user_dao.update_payment(
                                telegram_id=user.telegram_id,
                                last_payment_date=datetime.now().date(),
                                contribution=user.contribution,
                                status=user.status,
                                payment_method_id=user.payment_method_id
                            )
                            logger.info(f"Renewed subscription for user {user.telegram_id}")
                        else:
                            logger.warning(f"Failed to renew subscription for user {user.telegram_id}: {payment.status}")
                    except Exception as e:
                        logger.error(f"Error renewing subscription for user {user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error checking subscriptions: {e}")

def setup_scheduler():
    scheduler.add_job(
        check_subscriptions,
        trigger=CronTrigger(hour=0, minute=0),  # Каждый день в полночь
        id="check_subscriptions",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler set up")