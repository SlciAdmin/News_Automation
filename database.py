import psycopg2
from psycopg2 import pool, extras
from datetime import datetime
from config import Config
import logging
import pytz
import os

logger = logging.getLogger(__name__)
db_pool = None

def get_db_pool():
    """Get or create PostgreSQL connection pool"""
    global db_pool
    if db_pool is None:
        try:
            # Use DATABASE_URL if available (Render provides this)
            if hasattr(Config, 'DATABASE_URL') and Config.DATABASE_URL:
                logger.info("🔌 Connecting using DATABASE_URL")
                db_pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=Config.DATABASE_URL
                )
            else:
                logger.info("🔌 Connecting using individual parameters")
                db_pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    database=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD
                )
            logger.info("✅ PostgreSQL connection pool created")
        except Exception as e:
            logger.error(f"❌ Pool creation failed: {e}")
            raise
    return db_pool

def get_db_connection():
    """Get a connection from the pool"""
    return get_db_pool().getconn()

def release_db_connection(conn):
    """Return connection to the pool"""
    if conn:
        get_db_pool().putconn(conn)

def init_db():
    """Initialize PostgreSQL tables"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Subscribers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id SERIAL PRIMARY KEY,
            phone_number VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100),
            language_pref VARCHAR(20) DEFAULT 'both',
            is_active BOOLEAN DEFAULT TRUE,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_notified TIMESTAMP
        )
        ''')
        
        # Broadcast logs table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcast_logs (
            id SERIAL PRIMARY KEY,
            broadcast_date DATE NOT NULL,
            broadcast_time TIME,
            total_sent INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            english_audio_url TEXT,
            hindi_audio_url TEXT,
            english_duration INTEGER,
            hindi_duration INTEGER,
            triggered_by TEXT DEFAULT 'scheduler',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Admin logs table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id SERIAL PRIMARY KEY,
            action VARCHAR(50) NOT NULL,
            phone_number VARCHAR(20),
            admin_user VARCHAR(100),
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_phone ON subscribers(phone_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_active ON subscribers(is_active) WHERE is_active = TRUE')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_date ON broadcast_logs(broadcast_date)')
        
        conn.commit()
        logger.info("✅ Database tables initialized")
        return True
    except psycopg2.OperationalError as e:
        logger.error(f"❌ PostgreSQL connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ DB init error: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: release_db_connection(conn)


# =============================================================================
# ✅ DATABASE MIGRATION FUNCTION (Add missing columns safely)
# =============================================================================
def migrate_database():
    """Add missing columns to existing tables (run once - safe for production)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add duration columns if they don't exist (PostgreSQL safe migration using DO block)
        cursor.execute('''
        DO $$ 
        BEGIN 
            -- Add english_duration column if not exists
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'broadcast_logs' 
                AND column_name = 'english_duration'
                AND table_schema = 'public'
            ) THEN
                ALTER TABLE broadcast_logs ADD COLUMN english_duration INTEGER DEFAULT 0;
                RAISE NOTICE 'Added column: english_duration';
            END IF;
            
            -- Add hindi_duration column if not exists
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'broadcast_logs' 
                AND column_name = 'hindi_duration'
                AND table_schema = 'public'
            ) THEN
                ALTER TABLE broadcast_logs ADD COLUMN hindi_duration INTEGER DEFAULT 0;
                RAISE NOTICE 'Added column: hindi_duration';
            END IF;
        END $$;
        ''')
        conn.commit()
        logger.info("✅ Database migration completed - duration columns verified/added")
        return True
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        if conn: 
            conn.rollback()
        return False
    finally:
        if conn: 
            release_db_connection(conn)


# =============================================================================
# SUBSCRIBER MANAGEMENT FUNCTIONS
# =============================================================================
def add_subscriber(phone_number, name=None, language='both'):
    """Add or update a subscriber"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Clean phone number
        clean = ''.join(filter(str.isdigit, phone_number))
        if clean.startswith('0'): clean = clean[1:]
        if not clean.startswith('91'): clean = '91' + clean
        
        # Upsert subscriber
        cursor.execute('''
        INSERT INTO subscribers (phone_number, name, language_pref, is_active, subscribed_at)
        VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
        ON CONFLICT (phone_number) DO UPDATE SET
            name = COALESCE(EXCLUDED.name, subscribers.name),
            language_pref = EXCLUDED.language_pref,
            is_active = TRUE,
            subscribed_at = CURRENT_TIMESTAMP
        ''', (clean, name, language))
        
        conn.commit()
        logger.info(f"✅ Added subscriber: {clean}")
        return True, "Subscriber added successfully"
    except Exception as e:
        logger.error(f"❌ Error adding subscriber: {e}")
        if conn: conn.rollback()
        return False, str(e)
    finally:
        if conn: release_db_connection(conn)

def remove_subscriber(phone_number):
    """Remove a subscriber by phone number"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        clean = ''.join(filter(str.isdigit, phone_number))
        if not clean.startswith('91'): clean = '91' + clean
        
        cursor.execute('DELETE FROM subscribers WHERE phone_number = %s', (clean,))
        affected = cursor.rowcount
        conn.commit()
        
        if affected > 0:
            logger.info(f"✅ Removed subscriber: {clean}")
            return True, "Subscriber removed"
        return False, "Subscriber not found"
    except Exception as e:
        logger.error(f"❌ Error removing subscriber: {e}")
        if conn: conn.rollback()
        return False, str(e)
    finally:
        if conn: release_db_connection(conn)

def get_active_subscribers():
    """Get all active subscribers"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute('''
        SELECT id, phone_number, name, language_pref, subscribed_at, last_notified
        FROM subscribers WHERE is_active = TRUE ORDER BY subscribed_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"❌ Error fetching subscribers: {e}")
        return []
    finally:
        if conn: release_db_connection(conn)

def get_subscriber_count():
    """Get count of active subscribers"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM subscribers WHERE is_active = TRUE')
        return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"❌ Error getting subscriber count: {e}")
        return 0
    finally:
        if conn: release_db_connection(conn)

def get_broadcast_history(limit=10):
    """Get recent broadcast logs"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute('''
        SELECT id, broadcast_date, broadcast_time, total_sent, total_failed, 
               english_duration, hindi_duration, triggered_by
        FROM broadcast_logs ORDER BY created_at DESC LIMIT %s
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"❌ Error fetching broadcast history: {e}")
        return []
    finally:
        if conn: release_db_connection(conn)

def log_broadcast(sent, failed, en_url, hi_url, triggered_by='scheduler', 
                  en_duration=0, hi_duration=0):
    """Log a broadcast attempt"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO broadcast_logs
        (broadcast_date, broadcast_time, total_sent, total_failed, 
         english_audio_url, hindi_audio_url, english_duration, hindi_duration, triggered_by)
        VALUES (CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s, %s)
        ''', (sent, failed, en_url, hi_url, en_duration, hi_duration, triggered_by))
        conn.commit()
        logger.info(f"📊 Broadcast logged: {sent} sent, {failed} failed")
    except Exception as e:
        logger.error(f"❌ Error logging broadcast: {e}")
        if conn: conn.rollback()
    finally:
        if conn: release_db_connection(conn)

def log_admin_action(action, phone, admin_user, details=None):
    """Log admin actions"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO admin_logs (action, phone_number, admin_user, details)
        VALUES (%s, %s, %s, %s)
        ''', (action, phone, admin_user, details))
        conn.commit()
        logger.info(f"👤 Admin action: {action} - {admin_user}")
    except Exception as e:
        logger.error(f"❌ Error logging admin action: {e}")
        if conn: conn.rollback()
    finally:
        if conn: release_db_connection(conn)

def get_ist_time():
    """Get current time in IST timezone"""
    return datetime.now(pytz.timezone(Config.TIMEZONE))

def close_db_pool():
    """Close all connections in the pool"""
    global db_pool
    if db_pool:
        db_pool.closeall()
        logger.info("✅ PostgreSQL connection pool closed")
        db_pool = None

# =============================================================================
# ✅ TEST DATABASE CONNECTION
# =============================================================================
def test_connection():
    """Test database connection"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        logger.info("✅ Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False
    finally:
        if conn:
            release_db_connection(conn)