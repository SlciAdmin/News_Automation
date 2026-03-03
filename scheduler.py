from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import pytz
from datetime import datetime
from config import Config
import database
import news_fetcher
import whatsapp_api
import os

logger = logging.getLogger(__name__)

def in_broadcast_window():
    """Check if current IST time is between 8:00 AM and 8:30 AM"""
    ist = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(ist)
    # Check if hour is 8 and minute is less than 30
    return now.hour == Config.SCHEDULE_START_HOUR and now.minute < 30

def run_broadcast_logic(triggered_by='scheduler'):
    logger.info(f"🎙️ BROADCAST STARTED ({triggered_by})")
    
    # Skip auto if outside 8:00-8:30 AM window
    if triggered_by == 'scheduler' and not in_broadcast_window():
        logger.info("⏰ Outside 8:00-8:30 AM window, skipping auto broadcast")
        return {"success": False, "message": "Outside scheduled window", "skipped": True}
    
    try:
        subscribers = database.get_active_subscribers()
        if not subscribers:
            return {"success": False, "message": "No subscribers"}
        
        wa = whatsapp_api.WhatsAppCloudAPI()
        if not wa.test_connection():
            return {"success": False, "message": "WhatsApp API failed"}
        
        audio_files = {}
        audio_durations = {}
        
        # Fetch Both English and Hindi
        for lang in ["english", "hindi"]:
            logger.info(f"🔍 Fetching {lang} bulletin...")
            bulletins = news_fetcher.fetch_audio_bulletins(lang)
            if bulletins:
                local = news_fetcher.download_audio(bulletins[0])
                if local:
                    audio_files[lang] = local
                    audio_durations[lang] = bulletins[0].get('duration', 0)
                    logger.info(f"✅ {lang} audio ready")
                else:
                    logger.error(f"❌ Failed to download {lang} audio")
            else:
                logger.error(f"❌ No {lang} bulletins found")
        
        if len(audio_files) < 2:
            return {"success": False, "message": "Audio download failed"}
        
        sent, failed = 0, 0
        ist = database.get_ist_time()
        date_str = ist.strftime("%d-%m-%Y")
        time_str = ist.strftime("%I:%M %p IST")
        
        for sub in subscribers:
            phone = ''.join(filter(str.isdigit, str(sub['phone_number'])))
            if not phone.startswith('91'): phone = '91' + phone
            if len(phone) != 12: continue
            
            try:
                # Header
                header = f"🎙️ *AIR Bulletin*\n📅 {date_str} | ⏰ {time_str}\n🇬🇧 English 👇"
                wa.send_text_message(phone, header)
                
                # English Audio
                wa._send_audio_with_upload(phone, audio_files['english'], is_local_path=True)
                
                # Hindi Separator
                wa.send_text_message(phone, "🇮🇳 Hindi 👇")
                
                # Hindi Audio
                wa._send_audio_with_upload(phone, audio_files['hindi'], is_local_path=True)
                
                # Footer
                wa.send_text_message(phone, "✅ Done!")
                
                sent += 1
                logger.info(f"✅ Sent to {phone}")
            except Exception as e:
                failed += 1
                logger.error(f"Failed {phone}: {e}")
        
        # Cleanup
        for path in audio_files.values():
            if os.path.exists(path): os.remove(path)
            
        database.log_broadcast(sent, failed, "direct", "direct", triggered_by, 
                               audio_durations.get('english', 0), audio_durations.get('hindi', 0))
        
        return {"success": True, "sent": sent, "failed": failed}
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return {"success": False, "error": str(e)}

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone(Config.TIMEZONE))
    
    # Schedule at 8:00 AM IST daily
    scheduler.add_job(
        func=run_broadcast_logic,
        trigger=CronTrigger(hour=Config.SCHEDULE_START_HOUR, minute=0),
        id='auto_broadcast_8am',
        kwargs={'triggered_by': 'scheduler'},
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"✅ Scheduler: {Config.SCHEDULE_START_HOUR}:00 AM IST daily")
    return scheduler

def stop_scheduler(sched):
    if sched: sched.shutdown()