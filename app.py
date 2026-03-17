from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import os
import atexit
import sys

from config import Config
import database
import scheduler

# ===== Initialize Flask App =====
app = Flask(__name__)
app.config.from_object(Config)
Config.create_dirs()

# ===== Logging Setup =====
if not os.path.exists(Config.LOG_DIR):
    os.makedirs(Config.LOG_DIR, exist_ok=True)

file_handler = RotatingFileHandler(
    os.path.join(Config.LOG_DIR, 'app.log'),
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
console_handler.setLevel(logging.INFO)
app.logger.addHandler(console_handler)

app.logger.setLevel(logging.INFO)
logger = app.logger

# Global scheduler variable
sched = None

# ===== Login Required Decorator =====
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ===== ROUTES =====

@app.route('/')
@login_required
def home():
    """Home dashboard"""
    subscribers = database.get_active_subscribers()
    count = database.get_subscriber_count()
    history = database.get_broadcast_history(limit=10)
    return render_template('index.html', 
                          subscribers=subscribers, 
                          count=count, 
                          history=history, 
                          config=Config)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session['logged_in'] = True
            session['admin_user'] = username
            database.log_admin_action('LOGIN', None, username, 'Logged in')
            logger.info(f"✅ Admin logged in: {username}")
            return redirect(url_for('home'))
        
        logger.warning(f"⚠️ Failed login attempt: {username}")
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Admin logout"""
    admin_user = session.get('admin_user')
    database.log_admin_action('LOGOUT', None, admin_user)
    logger.info(f"✅ Admin logged out: {admin_user}")
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/subscriber', methods=['POST'])
@login_required
def add_subscriber_api():
    """Add new subscriber via API"""
    data = request.get_json() or {}
    phone = data.get('phone_number')
    
    if not phone:
        return jsonify({'success': False, 'error': 'Phone number required'}), 400
    
    success, msg = database.add_subscriber(
        phone, 
        data.get('name'), 
        data.get('language', 'both')
    )
    
    if success:
        database.log_admin_action('ADD', phone, session.get('admin_user'))
        logger.info(f"✅ Added subscriber: {phone}")
        return jsonify({'success': True, 'message': msg})
    
    logger.error(f"❌ Failed to add {phone}: {msg}")
    return jsonify({'success': False, 'error': msg}), 400

@app.route('/api/subscriber/<path:phone>', methods=['DELETE'])
@login_required
def remove_subscriber_api(phone):
    """Remove subscriber via API"""
    success, msg = database.remove_subscriber(phone)
    
    if success:
        database.log_admin_action('REMOVE', phone, session.get('admin_user'))
        logger.info(f"✅ Removed subscriber: {phone}")
        return jsonify({'success': True, 'message': msg})
    
    logger.error(f"❌ Failed to remove {phone}: {msg}")
    return jsonify({'success': False, 'error': msg}), 404

@app.route('/api/test-whatsapp', methods=['GET'])
@login_required
def test_whatsapp():
    """Test WhatsApp API connection"""
    from whatsapp_api import WhatsAppCloudAPI
    wa = WhatsAppCloudAPI()
    success = wa.test_connection()
    logger.info(f"WhatsApp test: {'✅ success' if success else '❌ failed'}")
    return jsonify({
        'success': success, 
        'message': 'Connected ✓' if success else 'Failed ✗'
    })

@app.route('/api/trigger-broadcast', methods=['POST'])
@login_required
def trigger_broadcast():
    """✅ MANUAL TRIGGER: Fetch headlines → TTS → WhatsApp Audio"""
    admin_user = session.get('admin_user')
    logger.info(f"🎙️ Broadcast triggered by: {admin_user}")
    
    try:
        # Import here to avoid circular imports
        from scheduler import run_headlines_tts_broadcast
        result = run_headlines_tts_broadcast(triggered_by=f"admin:{admin_user}")
        return jsonify(result), 200
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return jsonify({'success': False, 'error': 'Module not found'}), 500
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
@login_required
def status():
    """Get system status"""
    from whatsapp_api import WhatsAppCloudAPI
    wa = WhatsAppCloudAPI()
    ist = database.get_ist_time()
    
    status_data = {
        'subscribers': database.get_subscriber_count(),
        'whatsapp_connected': wa.test_connection(),
        'scheduler_active': sched is not None and getattr(sched, 'running', False),
        'current_time_ist': ist.strftime("%Y-%m-%d %H:%M:%S"),
        'broadcast_window': f"{Config.SCHEDULE_START_HOUR}:00 - {Config.SCHEDULE_END_HOUR}:00 IST",
    }
    return jsonify(status_data)

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """WhatsApp webhook verification"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == Config.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified")
        return challenge, 200
    
    logger.warning("❌ Webhook verification failed")
    return 'Verification failed', 403

@app.route('/webhook', methods=['POST'])
def webhook_receive():
    """Receive WhatsApp webhook events"""
    data = request.get_json()
    logger.info(f"📥 Webhook received: {data}")
    return jsonify({'status': 'ok'}), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check for Render/Uptime"""
    try:
        db_ok = database.get_subscriber_count() is not None
        sched_ok = sched is not None and getattr(sched, 'running', False)
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected' if db_ok else 'error',
            'scheduler': 'running' if sched_ok else 'stopped',
            'timestamp': database.get_ist_time().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# ===== Error Handlers =====
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404: {error}")
    return jsonify({'error': 'Not found', 'path': request.path}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500: {error}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500

# ===== Cleanup on Exit =====
@atexit.register
def cleanup():
    global sched
    logger.info("🛑 Shutting down...")
    if sched:
        scheduler.stop_scheduler(sched)
    database.close_db_pool()
    logger.info("✅ Cleanup complete")

# ===== Application Entry Point =====
if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 Starting Broadcast App")
    logger.info("=" * 60)
    
    # Initialize database
    if not database.init_db():
        logger.error("❌ Database init failed")
        sys.exit(1)
    
    # Start scheduler
    try:
        sched = scheduler.start_scheduler()
        logger.info("✅ Scheduler started")
    except Exception as e:
        logger.error(f"⚠️ Scheduler error: {e}")
        sched = None
    
    # Run Flask
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"✅ App ready on http://0.0.0.0:{port}")
    
    app.run(
        debug=Config.DEBUG,
        host='0.0.0.0',
        port=port,
        use_reloader=False
    )