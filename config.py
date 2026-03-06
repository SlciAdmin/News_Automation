import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# ===== Load .env with explicit path =====
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)

class Config:
    # =============================================================================
    # 🗄️ PostgreSQL Database Configuration
    # =============================================================================
    DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
    
    if DATABASE_URL:
        # Render/Cloud PostgreSQL - parse from URL or use separate vars
        DB_HOST = os.getenv('DB_HOST', '').strip()
        DB_PORT = os.getenv('DB_PORT', '5432').strip()
        DB_NAME = os.getenv('DB_NAME', '').strip()
        DB_USER = os.getenv('DB_USER', '').strip()
        DB_PASSWORD = os.getenv('DB_PASSWORD', '').strip()
    else:
        # Local development fallback
        DB_HOST = os.getenv('DB_HOST', '127.0.0.1').strip()
        DB_PORT = os.getenv('DB_PORT', '5432').strip()
        DB_NAME = os.getenv('DB_NAME', 'broadcast_db').strip()
        DB_USER = os.getenv('DB_USER', 'postgres').strip()
        DB_PASSWORD = os.getenv('DB_PASSWORD', '').strip()
        
        # Build DATABASE_URL for SQLAlchemy
        if DB_PASSWORD:
            encoded_password = quote_plus(DB_PASSWORD)
            DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        else:
            DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # =============================================================================
    # 📱 WhatsApp Cloud API Configuration
    # =============================================================================
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '').strip()
    WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID', '').strip()
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '').strip()
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'dev_verify_token').strip()
    WHATSAPP_API_BASE = os.getenv('WHATSAPP_API_BASE', 'https://graph.facebook.com/v19.0').strip()
    
    # =============================================================================
    # 🔐 Admin Credentials
    # =============================================================================
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin').strip()
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '').strip()
    
    # =============================================================================
    # ⚙️ Flask Application Settings
    # =============================================================================
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_change_me_in_production').strip()
    DEBUG = os.getenv('FLASK_ENV', 'development').lower() != 'production'
    FLASK_ENV = os.getenv('FLASK_ENV', 'development').strip()
    
    # =============================================================================
    # 📁 Directory Paths
    # =============================================================================
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    AUDIO_DIR = os.path.join(BASE_DIR, 'audio_downloads')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    
    # =============================================================================
    # ⏰ SCHEDULE SETTINGS - KEY UPDATE
    # =============================================================================
    # 🎯 Broadcast SEND time: 9:00 AM IST (when WhatsApp messages go out)
    SCHEDULE_START_HOUR = int(os.getenv('SCHEDULE_START_HOUR', '9'))   # 9 AM
    SCHEDULE_END_HOUR = int(os.getenv('SCHEDULE_END_HOUR', '10'))       # 10 AM window
    SCHEDULE_INTERVAL_MINUTES = int(os.getenv('SCHEDULE_INTERVAL_MINUTES', '15'))
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata').strip()
    
    # 📰 NEWS FETCH time: 7:00-7:30 AM IST (separate logic in news_fetcher.py)
    # This is handled in news_fetcher.py URL parameters, not in config
    NEWS_FETCH_TIME_SLOT = os.getenv('NEWS_FETCH_TIME_SLOT', '07:00-07:30').strip()
    
    # =============================================================================
    # 📰 News Source URLs (Both Languages)
    # =============================================================================
    NEWS_SOURCE_BASE = os.getenv('NEWS_SOURCE_BASE', 'https://www.newsonair.gov.in/national-bulletins/').strip()
    NEWS_SOURCE_ENGLISH = f"{NEWS_SOURCE_BASE}?listen_news_cat=&listen_news_lang=english&listen_news_date=&listen_news_time=&submit=Search"
    NEWS_SOURCE_HINDI = f"{NEWS_SOURCE_BASE}?listen_news_cat=&listen_news_lang=hindi&listen_news_date=&listen_news_time=&submit=Search"
    
    # =============================================================================
    # 🎵 Audio Processing Settings - NO TRIMMING NEEDED
    # =============================================================================
    # ✅ Audio is already max 5 minutes from AIR - no trimming required
    MIN_AUDIO_DURATION_SECONDS = int(os.getenv('MIN_AUDIO_DURATION_SECONDS', '60'))    # 1 minute minimum
    MAX_AUDIO_DURATION_SECONDS = int(os.getenv('MAX_AUDIO_DURATION_SECONDS', '300'))   # 5 minutes maximum
    ALLOW_LONGER_AUDIO = os.getenv('ALLOW_LONGER_AUDIO', 'false').lower() == 'true'
    AUTO_TRIM_AUDIO = os.getenv('AUTO_TRIM_AUDIO', 'false').lower() == 'true'          # ❌ Disabled per requirement
    
    # =============================================================================
    # 🌐 Audio Hosting Services
    # =============================================================================
    AUDIO_HOST_SERVICE = os.getenv('AUDIO_HOST_SERVICE', 'catbox').strip()  # Options: catbox, pixeldrain, file.io, own_server
    AUDIO_HOST_BASE_URL = os.getenv('AUDIO_HOST_BASE_URL', '').strip()      # For own_server option
    
    # =============================================================================
    # 🔧 Helper Methods
    # =============================================================================
    @classmethod
    def create_dirs(cls):
        """Create required directories if they don't exist"""
        os.makedirs(cls.AUDIO_DIR, exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)
    
    @classmethod
    def validate(cls):
        """Validate critical configuration values"""
        errors = []
        
        # Database
        if not cls.DB_NAME and not cls.DATABASE_URL:
            errors.append("❌ Database configuration is required (DB_NAME or DATABASE_URL)")
        
        # WhatsApp API
        if not cls.WHATSAPP_PHONE_NUMBER_ID:
            errors.append("❌ WHATSAPP_PHONE_NUMBER_ID is required")
        if not cls.WHATSAPP_ACCESS_TOKEN or len(cls.WHATSAPP_ACCESS_TOKEN) < 50:
            errors.append("❌ WHATSAPP_ACCESS_TOKEN is invalid or missing")
        
        # Admin
        if not cls.ADMIN_PASSWORD:
            errors.append("❌ ADMIN_PASSWORD is required")
        
        # Schedule
        if cls.SCHEDULE_START_HOUR < 0 or cls.SCHEDULE_START_HOUR > 23:
            errors.append("❌ SCHEDULE_START_HOUR must be 0-23")
        
        return errors
    
    @classmethod
    def log_config_summary(cls, logger=None):
        """Log non-sensitive config summary for debugging"""
        if logger is None:
            import logging
            logger = logging.getLogger(__name__)
        
        logger.info("🔧 Configuration Summary:")
        logger.info(f"   • Environment: {'production' if not cls.DEBUG else 'development'}")
        logger.info(f"   • Database: {cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}")
        logger.info(f"   • WhatsApp API: {cls.WHATSAPP_API_BASE}")
        logger.info(f"   • Broadcast Window: {cls.SCHEDULE_START_HOUR}:00 - {cls.SCHEDULE_END_HOUR}:00 {cls.TIMEZONE}")
        logger.info(f"   • News Fetch Slot: {cls.NEWS_FETCH_TIME_SLOT}")
        logger.info(f"   • Audio Duration: {cls.MIN_AUDIO_DURATION_SECONDS}-{cls.MAX_AUDIO_DURATION_SECONDS}s")
        logger.info(f"   • Auto Trim: {cls.AUTO_TRIM_AUDIO}")
        logger.info(f"   • Audio Host: {cls.AUDIO_HOST_SERVICE}")