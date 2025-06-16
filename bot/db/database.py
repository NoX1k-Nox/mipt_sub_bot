from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dao.models import Base
from pathlib import Path
import os

# DB_PATH = os.path.abspath("database.db")
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "database.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"Database path: {DB_PATH}")
print(f"Data folder exists: {os.path.exists(os.path.dirname(DB_PATH))}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
