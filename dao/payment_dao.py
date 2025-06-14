from sqlalchemy.orm import sessionmaker
from dao.models import Payment, engine
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

Session = sessionmaker(bind=engine)

class PaymentDAO:
    def __init__(self):
        self.session = Session()

    def save_payment(self, payment_id: str, yookassa_id: str, telegram_id: int, status: str = "pending"):
        try:
            payment = Payment(
                payment_id=payment_id,
                yookassa_id=yookassa_id,
                telegram_id=telegram_id,
                status=status,
                created_at=datetime.utcnow()
            )
            self.session.add(payment)
            self.session.commit()
            logger.info(f"Saved payment: payment_id={payment_id}, yookassa_id={yookassa_id}, telegram_id={telegram_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving payment {payment_id}: {e}")

    def get_yookassa_id(self, payment_id: str) -> str:
        try:
            payment = self.session.query(Payment).filter_by(payment_id=payment_id).first()
            if payment:
                return payment.yookassa_id
            logger.warning(f"YooKassa ID not found for payment_id={payment_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving YooKassa ID for payment_id={payment_id}: {e}")
            return None

    def update_payment_status(self, yookassa_id: str, status: str) -> bool:
        try:
            payment = self.session.query(Payment).filter_by(yookassa_id=yookassa_id).first()
            if payment:
                payment.status = status
                self.session.commit()
                logger.info(f"Updated payment status: yookassa_id={yookassa_id}, status={status}")
                return True
            logger.warning(f"No payment found for yookassa_id={yookassa_id}")
            return False
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating payment status for yookassa_id={yookassa_id}: {e}")
            return False
