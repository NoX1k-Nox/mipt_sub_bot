import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "phystech_union_bot"
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")

SUPPORT_URL = os.getenv("SUPPORT_URL")
NEWS_CHAT_URL = os.getenv("NEWS_CHAT_URL")
PARTNERS_CHAT_URL = os.getenv("PARTNERS_CHAT_URL")
MEMBERS_CHAT_URL = os.getenv("MEMBERS_CHAT_URL")
DOGOVOR_URL = os.getenv("DOGOVOR_URL")

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

SECRET_TOKEN = os.getenv("SECRET_TOKEN", "your_secret_token")
WEBHOOK_PATH = f"/{BOT_TOKEN}"
YOOKASSA_WEBHOOK_PATH = "/yookassa"
DB_PATH = os.getenv("DB_PATH", "database.db")
