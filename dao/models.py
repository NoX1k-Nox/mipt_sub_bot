from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from datetime import datetime
import os

# Определяем путь к базе данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'data', 'database.db')
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    telegram_id = Column(Integer, primary_key=True)
    last_name = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    patronymic = Column(String)
    status = Column(String, nullable=False)
    contribution = Column(Integer)
    last_payment_date = Column(DateTime)
    payment_method_id = Column(String)  # Для рекуррентных платежей

class Payment(Base):
    __tablename__ = 'payments'
    payment_id = Column(String, primary_key=True)
    yookassa_id = Column(String, unique=True)
    telegram_id = Column(Integer, ForeignKey('users.telegram_id'))
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Создаём таблицы в базе данных
Base.metadata.create_all(engine)
