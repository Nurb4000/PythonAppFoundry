import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


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
