from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import os
import atexit
from config import Config
import database
import scheduler
import sys

app = Flask(__name__)
app.config.from_object(Config)
Config.create_dirs()

# ===== Logging Setup =====
# Create logs directory if it doesn't exist
if not os.path.exists(Config.LOG_DIR):
    os.makedirs(Config.LOG_DIR, exist_ok=True)

# File handler for persistent logs
file_handler = RotatingFileHandler(
    os.path.join(Config.LOG_DIR, 'app.log'),
    maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

# Console handler for Render logs (stdout)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
console_handler.setLevel(logging.INFO)
app.logger.addHandler(console_handler)

# Set root logger level
app.logger.setLevel(logging.INFO)

sched = None

# ===== Login Required Decorator =====
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ===== Routes =====
@app.route('/')
@login_required
def home():
    subscribers = database.get_active_subscribers()
    count = database.get_subscriber_count()
    history = database.get_broadcast_history(limit=10)
    return render_template('index.html', subscribers=subscribers, count=count, history=history, config=Config)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if (request.form.get('username') == Config.ADMIN_USERNAME and
            request.form.get('password') == Config.ADMIN_PASSWORD):
            session['logged_in'] = True
            session['admin_user'] = request.form.get('username')
            database.log_admin_action('LOGIN', None, session['admin_user'], 'Logged in')
            app.logger.info(f"Admin logged in: {session['admin_user']}")
            return redirect(url_for('home'))
        app.logger.warning(f"Failed login attempt for username: {request.form.get('username')}")
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    admin_user = session.get('admin_user')
    database.log_admin_action('LOGOUT', None, admin_user)
    app.logger.info(f"Admin logged out: {admin_user}")
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/subscriber', methods=['POST'])
@login_required
def add_subscriber_api():
    data = request.get_json()
    phone = data.get('phone_number')
    if not phone:
        return jsonify({'success': False, 'error': 'Phone number required'}), 400
    
    success, msg = database.add_subscriber(phone, data.get('name'), data.get('language', 'both'))
    if success:
        database.log_admin_action('ADD', phone, session.get('admin_user'))
        app.logger.info(f"Admin {session.get('admin_user')} added subscriber: {phone}")
        return jsonify({'success': True, 'message': msg})
    app.logger.error(f"Failed to add subscriber {phone}: {msg}")
    return jsonify({'success': False, 'error': msg}), 400

@app.route('/api/subscriber/<path:phone>', methods=['DELETE'])
@login_required
def remove_subscriber_api(phone):
    success, msg = database.remove_subscriber(phone)
    if success:
        database.log_admin_action('REMOVE', phone, session.get('admin_user'))
        app.logger.info(f"Admin {session.get('admin_user')} removed subscriber: {phone}")
        return jsonify({'success': True, 'message': msg})
    app.logger.error(f"Failed to remove subscriber {phone}: {msg}")
    return jsonify({'success': False, 'error': msg}), 404

@app.route('/api/test-whatsapp')
@login_required
def test_whatsapp():
    from whatsapp_api import WhatsAppCloudAPI
    wa = WhatsAppCloudAPI()
    success = wa.test_connection()
    app.logger.info(f"WhatsApp connection test: {'success' if success else 'failed'}")
    return jsonify({'success': success, 'message': 'Connected ✓' if success else 'Failed ✗'})

@app.route('/api/trigger-broadcast', methods=['POST'])
@login_required
def trigger_broadcast():
    """Manual broadcast trigger - works anytime"""
    admin_user = session.get('admin_user')
    app.logger.info(f"Manual broadcast triggered by admin: {admin_user}")
    
    try:
        result = scheduler.run_broadcast_logic(triggered_by=f"admin:{admin_user}")
        app.logger.info(f"Manual broadcast result: {result}")
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Manual broadcast error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status')
@login_required
def status():
    from whatsapp_api import WhatsAppCloudAPI
    wa = WhatsAppCloudAPI()
    ist = database.get_ist_time()
    in_window = scheduler.in_broadcast_window()
    
    # Get subscriber count
    subscriber_count = database.get_subscriber_count()
    
    # Test WhatsApp connection
    whatsapp_connected = wa.test_connection()
    
    status_data = {
        'subscribers': subscriber_count,
        'whatsapp_connected': whatsapp_connected,
        'scheduler_active': sched is not None and getattr(sched, 'running', False),
        'current_time_ist': ist.strftime("%Y-%m-%d %H:%M:%S"),
        'broadcast_window': f"{Config.SCHEDULE_START_HOUR}:00 - {Config.SCHEDULE_END_HOUR}:00 IST",
        'auto_active': in_window,
        'next_run': f"Every {Config.SCHEDULE_INTERVAL_MINUTES} min during window",
        'audio_duration_min': f"{Config.MIN_AUDIO_DURATION_SECONDS/60:.0f} min",
        'audio_duration_max': f"{Config.MAX_AUDIO_DURATION_SECONDS/60:.0f} min"
    }
    
    app.logger.debug(f"Status check: {status_data}")
    return jsonify(status_data)

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """WhatsApp webhook verification"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    app.logger.info(f"Webhook verification request - mode: {mode}, token: {token}")
    
    if mode == 'subscribe' and token == Config.WHATSAPP_VERIFY_TOKEN:
        app.logger.info("Webhook verified successfully")
        return challenge, 200
    
    app.logger.warning(f"Webhook verification failed - token mismatch")
    return 'Verification failed', 403

@app.route('/webhook', methods=['POST'])
def webhook_receive():
    """Receive WhatsApp webhook events"""
    data = request.get_json()
    app.logger.info(f"Webhook received: {data}")
    
    # Process incoming messages here if needed
    # For now, just acknowledge receipt
    
    return jsonify({'status': 'ok'}), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render"""
    try:
        # Check database connection
        db_status = database.get_subscriber_count() is not None
        
        # Check if scheduler is running
        scheduler_status = sched is not None and getattr(sched, 'running', False)
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected' if db_status else 'error',
            'scheduler': 'running' if scheduler_status else 'stopped',
            'timestamp': database.get_ist_time().isoformat()
        }), 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ===== Error Handlers =====
@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f"404 error: {error}")
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 error: {error}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500

# ===== Cleanup on Exit =====
@atexit.register
def cleanup():
    """Cleanup resources on application shutdown"""
    global sched
    app.logger.info("Shutting down application...")
    
    if sched:
        app.logger.info("Stopping scheduler...")
        scheduler.stop_scheduler(sched)
    
    app.logger.info("Closing database connections...")
    database.close_db_pool()
    
    app.logger.info("Cleanup complete")

# ===== Application Entry Point =====
if __name__ == '__main__':
    # Log startup
    app.logger.info("=" * 60)
    app.logger.info("🚀 Starting Broadcast Admin Application")
    app.logger.info("=" * 60)
    
    # Log configuration (without sensitive data)
    app.logger.info(f"Environment: {'production' if not Config.DEBUG else 'development'}")
    app.logger.info(f"Database: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    app.logger.info(f"Audio directory: {Config.AUDIO_DIR}")
    app.logger.info(f"Log directory: {Config.LOG_DIR}")
    
    # Initialize database
    app.logger.info("Initializing database...")
    if not database.init_db():
        app.logger.error("❌ Database initialization failed. Check PostgreSQL credentials in .env")
        import sys
        sys.exit(1)
    
    # Run database migration to add missing columns
    app.logger.info("Running database migration...")
    try:
        if database.migrate_database():
            app.logger.info("✅ Database migration completed successfully")
        else:
            app.logger.warning("⚠️ Database migration had issues - continuing anyway")
    except Exception as e:
        app.logger.error(f"Migration error: {e}")
    
    # Start auto-scheduler
    app.logger.info("Starting scheduler...")
    try:
        sched = scheduler.start_scheduler()
        app.logger.info("✅ Scheduler started successfully")
    except Exception as e:
        app.logger.error(f"❌ Failed to start scheduler: {e}")
        sched = None
    
    # Log broadcast schedule
    app.logger.info(f"⏰ Auto-broadcast: {Config.SCHEDULE_START_HOUR}:00 AM IST")
    app.logger.info(f"🔄 Interval: Every {Config.SCHEDULE_INTERVAL_MINUTES} minutes during window")
    app.logger.info(f"🎵 Audio Duration: {Config.MIN_AUDIO_DURATION_SECONDS/60:.0f}-{Config.MAX_AUDIO_DURATION_SECONDS/60:.0f} minutes")
    
    # Get subscriber count
    sub_count = database.get_subscriber_count()
    app.logger.info(f"👥 Active subscribers: {sub_count}")
    
    app.logger.info("=" * 60)
    app.logger.info(f"✅ Application ready! Listening on http://0.0.0.0:5000")
    app.logger.info("=" * 60)
    
    # Run the app
    app.run(
        debug=Config.DEBUG,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),  # Use PORT from environment (Render sets this)
        use_reloader=False  # Disable reloader in production
    )