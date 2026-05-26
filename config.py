import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "careconnect-dev-secret-key-12345"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Default to False — must explicitly set DEBUG=True in .env for dev
    DEBUG = os.environ.get("DEBUG", "False").lower() in {"1", "true", "yes", "on"}
    TEMPLATES_AUTO_RELOAD = True

    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", SUPABASE_URL)

    MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017")
    MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "careconnect")

    # JWT settings (read in app.py directly from os.environ for flexibility)
    JWT_SECRET = os.environ.get("JWT_SECRET") or SECRET_KEY
    JWT_ACCESS_EXPIRES_HOURS = int(os.environ.get("JWT_ACCESS_EXPIRES_HOURS", "24"))
    JWT_REFRESH_EXPIRES_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRES_DAYS", "30"))
