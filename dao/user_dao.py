from sqlalchemy.orm import sessionmaker
from dao.models import User, engine
from datetime import datetime, date
import logging
import pandas as pd
import os

logger = logging.getLogger(__name__)

Session = sessionmaker(bind=engine)

class UserDAO:
    def __init__(self):
        self.session = Session()
        self.user_cache = {}
        self.csv_path = os.path.join(os.path.dirname(__file__), '..', 'users.csv')
        self.load_users_from_csv()

    def load_users_from_csv(self):
        try:
            if os.path.exists(self.csv_path):
                df = pd.read_csv(self.csv_path)
                for _, row in df.iterrows():
                    telegram_id = int(row['telegram_id'])
                    user = self.session.query(User).filter_by(telegram_id=telegram_id).first()
                    if not user:
                        last_payment_date = pd.to_datetime(row.get('last_payment_date')).to_pydatetime() if pd.notna(row.get('last_payment_date')) else None
                        user = User(
                            telegram_id=telegram_id,
                            last_name=str(row['last_name']),
                            first_name=str(row['first_name']),
                            patronymic=str(row['patronymic']) if pd.notna(row.get('patronymic')) else None,
                            status=str(row['status']),
                            contribution=int(row['contribution']),
                            last_payment_date=last_payment_date,
                            payment_method_id=str(row['payment_method_id']) if pd.notna(row.get('payment_method_id')) else None
                        )
                        self.session.add(user)
                    self.user_cache[telegram_id] = user
                self.session.commit()
                logger.info(f"Loaded {len(df)} users from users.csv")
            else:
                logger.warning("users.csv not found")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error loading users.csv: {e}")

    def save_users_to_csv(self):
        try:
            users = self.get_all_users()
            data = [{
                'telegram_id': user.telegram_id,
                'last_name': user.last_name,
                'first_name': user.first_name,
                'patronymic': user.patronymic,
                'status': user.status,
                'contribution': user.contribution,
                'last_payment_date': user.last_payment_date.isoformat() if user.last_payment_date else None,
                'payment_method_id': user.payment_method_id
            } for user in users]
            df = pd.DataFrame(data)
            df.to_csv(self.csv_path, index=False)
            logger.info(f"Saved {len(data)} users to users.csv")
        except Exception as e:
            logger.error(f"Error saving to users.csv: {e}")

    def get_user(self, telegram_id: int) -> User:
        telegram_id = int(telegram_id)
        if telegram_id in self.user_cache:
            return self.user_cache[telegram_id]
        user = self.session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            self.user_cache[telegram_id] = user
        return user

    def create_user(self, telegram_id: int, last_name: str, first_name: str, patronymic: str, status: str, contribution: int) -> bool:
        try:
            user = User(
                telegram_id=telegram_id,
                last_name=last_name,
                first_name=first_name,
                patronymic=patronymic,
                status=status,
                contribution=contribution
            )
            self.session.add(user)
            self.session.commit()
            self.user_cache[telegram_id] = user
            self.save_users_to_csv()
            logger.info(f"Created user {telegram_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating user {telegram_id}: {e}")
            return False

    def update_payment(self, telegram_id: int, last_payment_date: date, contribution: int, status: str, payment_method_id: str = None) -> bool:
        try:
            user = self.session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.last_payment_date = datetime.combine(last_payment_date, datetime.min.time())
                user.contribution = contribution
                user.status = status
                if payment_method_id:
                    user.payment_method_id = payment_method_id
                self.session.commit()
                self.user_cache[telegram_id] = user
                self.save_users_to_csv()
                logger.info(f"Updated payment for user {telegram_id}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating payment for user {telegram_id}: {e}")
            return False

    def get_all_users(self):
        try:
            users = self.session.query(User).all()
            logger.info(f"Retrieved {len(users)} users")
            return users
        except Exception as e:
            logger.error(f"Error retrieving users: {e}")
            return []
