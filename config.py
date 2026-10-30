import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "coaching-secret-key-change-in-production-2026")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/coaching_db")
    DB_NAME = os.getenv("DB_NAME", "coaching_db")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
