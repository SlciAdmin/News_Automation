import os
from dotenv import load_dotenv

# Load .env file with explicit path and error handling
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)

class Config:
    # ===== PostgreSQL Database - Support Render PostgreSQL =====
    DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
    
    # Parse DATABASE_URL if provided (Render provides this)
    if DATABASE_URL:
        # For Render PostgreSQL, DATABASE_URL is provided automatically
        DB_HOST = os.getenv('DB_HOST', '')
        DB_PORT = os.getenv('DB_PORT', '5432')
        DB_NAME = os.getenv('DB_NAME', '')
        DB_USER = os.getenv('DB_USER', '')
        DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    else:
        # Local development fallback
        DB_HOST = os.getenv('DB_HOST', '127.0.0.1').strip()
        DB_PORT = os.getenv('DB_PORT', '5432').strip()
        DB_NAME = os.getenv('DB_NAME', 'broadcast_db').strip()
        DB_USER = os.getenv('DB_USER', 'postgres').strip()
        DB_PASSWORD = os.getenv('DB_PASSWORD', '').strip()
        
        # Build DATABASE_URL
        if DB_PASSWORD:
            from urllib.parse import quote_plus
            encoded_password = quote_plus(DB_PASSWORD)
            DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        else:
            DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # ===== WhatsApp Cloud API =====
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '').strip()
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '').strip()
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'dev_verify_token').strip()
    WHATSAPP_API_BASE = os.getenv('WHATSAPP_API_BASE', 'https://graph.facebook.com/v19.0').strip()
    
    # ===== Admin =====
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin').strip()
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123').strip()
    
    # ===== App =====
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_change_me').strip()
    DEBUG = os.getenv('FLASK_ENV', 'development').lower() != 'production'
    
    # ===== Paths =====
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    AUDIO_DIR = os.path.join(BASE_DIR, 'audio_downloads')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    
    # ===== Schedule: Auto 9 AM IST =====
    SCHEDULE_START_HOUR = int(os.getenv('SCHEDULE_START_HOUR', '9'))
    SCHEDULE_END_HOUR = int(os.getenv('SCHEDULE_END_HOUR', '9'))
    SCHEDULE_INTERVAL_MINUTES = int(os.getenv('SCHEDULE_INTERVAL_MINUTES', '15'))
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata').strip()
    
    # ===== News =====
    NEWS_SOURCE_URL = os.getenv('NEWS_SOURCE_URL', 'https://www.newsonair.gov.in/national-bulletins/').strip()
    
    # ===== Audio Hosting =====
    AUDIO_HOST_SERVICE = os.getenv('AUDIO_HOST_SERVICE', 'catbox').strip()
    AUDIO_HOST_BASE_URL = os.getenv('AUDIO_HOST_BASE_URL', '').strip()
    
    # ===== Audio Duration Limits (4-5 minutes) =====
    MIN_AUDIO_DURATION_SECONDS = int(os.getenv('MIN_AUDIO_DURATION_SECONDS', '240'))
    MAX_AUDIO_DURATION_SECONDS = int(os.getenv('MAX_AUDIO_DURATION_SECONDS', '300'))
    
    @classmethod
    def create_dirs(cls):
        """Create required directories if they don't exist"""
        os.makedirs(cls.AUDIO_DIR, exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)
    
    @classmethod
    def validate(cls):
        """Validate critical config values"""
        errors = []
        if not cls.DB_NAME and not cls.DATABASE_URL:
            errors.append("Database configuration is required")
        if not cls.WHATSAPP_PHONE_NUMBER_ID:
            errors.append("WHATSAPP_PHONE_NUMBER_ID is required")
        if not cls.WHATSAPP_ACCESS_TOKEN or len(cls.WHATSAPP_ACCESS_TOKEN) < 50:
            errors.append("WHATSAPP_ACCESS_TOKEN is invalid or missing")
        if not cls.ADMIN_PASSWORD:
            errors.append("ADMIN_PASSWORD is required")
        return errors