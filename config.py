import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)

class Config:
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
    if DATABASE_URL:
        DB_HOST = os.getenv('DB_HOST', '').strip()
        DB_PORT = os.getenv('DB_PORT', '5432').strip()
        DB_NAME = os.getenv('DB_NAME', '').strip()
        DB_USER = os.getenv('DB_USER', '').strip()
        DB_PASSWORD = os.getenv('DB_PASSWORD', '').strip()
    else:
        DB_HOST = os.getenv('DB_HOST', '127.0.0.1').strip()
        DB_PORT = os.getenv('DB_PORT', '5432').strip()
        DB_NAME = os.getenv('DB_NAME', 'broadcast_db').strip()
        DB_USER = os.getenv('DB_USER', 'postgres').strip()
        DB_PASSWORD = os.getenv('DB_PASSWORD', '').strip()

    if DB_PASSWORD:
        encoded_password = quote_plus(DB_PASSWORD)
        DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # WhatsApp API
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '').strip()
    WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID', '').strip()
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '').strip()
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'dev_verify_token').strip()
    WHATSAPP_API_BASE = os.getenv('WHATSAPP_API_BASE', 'https://graph.facebook.com/v19.0').strip()

    # Admin
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin').strip()
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '').strip()

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_change_me_in_production').strip()
    DEBUG = os.getenv('FLASK_ENV', 'development').lower() != 'production'

    # Directories
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    AUDIO_DIR = os.path.join(BASE_DIR, 'audio_downloads')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    TTS_DIR = os.path.join(BASE_DIR, 'tts_output')

    # Schedule
    SCHEDULE_START_HOUR = int(os.getenv('SCHEDULE_START_HOUR', '9'))
    SCHEDULE_END_HOUR = int(os.getenv('SCHEDULE_END_HOUR', '10'))
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata').strip()

    # News Source
    NEWS_SOURCE_BASE = os.getenv('NEWS_SOURCE_BASE', 'https://www.newsonair.gov.in/bulletins-detail-category/morning-news/').strip()

    # TTS Voices (Human-like Azure Neural)
    TTS_ENGLISH_VOICE = os.getenv('TTS_ENGLISH_VOICE', 'en-US-AriaNeural').strip()
    TTS_HINDI_VOICE = os.getenv('TTS_HINDI_VOICE', 'hi-IN-SwaraNeural').strip()
    TTS_RATE = os.getenv('TTS_RATE', '+0%').strip()
    TTS_VOLUME = os.getenv('TTS_VOLUME', '+0%').strip()
    TTS_PITCH = os.getenv('TTS_PITCH', '+0Hz').strip()

    @classmethod
    def create_dirs(cls):
        os.makedirs(cls.AUDIO_DIR, exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)
        os.makedirs(cls.TTS_DIR, exist_ok=True)