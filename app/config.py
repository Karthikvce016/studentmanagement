"""Application configuration — reads from .env file."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────
from urllib.parse import quote_plus
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))  # encode special chars like @
DB_NAME = os.getenv("DB_NAME", "sms_db")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ── JWT ───────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY or JWT_SECRET_KEY.startswith("super-secret"):
    logging.warning(
        "⚠️  JWT_SECRET_KEY is weak or missing! Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
    # Allow startup for development, but warn loudly
    JWT_SECRET_KEY = JWT_SECRET_KEY or "dev-only-fallback-key-CHANGE-ME"

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# ── Logging ───────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
