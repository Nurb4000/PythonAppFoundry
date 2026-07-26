import os
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _validate_config():
    """Warn about insecure default configuration values."""
    secret_key = os.environ.get('SECRET_KEY', '')
    if not secret_key or secret_key == 'change-this-in-production':
        logger.warning(
            'SECURITY: SECRET_KEY is using the default value. '
            'Set a strong random SECRET_KEY in your .env file for production.'
        )
    
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        logger.info('Using default SQLite database at data.db')


_validate_config()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR / "data.db"}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    LLAMA_CPP_URL = os.environ.get('LLAMA_CPP_URL', 'http://localhost:8080')
    LLAMA_CPP_MODEL = os.environ.get('LLAMA_CPP_MODEL', '')
    AI_MAX_TOKENS = int(os.environ.get('AI_MAX_TOKENS', '4096'))
    AI_TEMPERATURE = float(os.environ.get('AI_TEMPERATURE', '0.7'))
