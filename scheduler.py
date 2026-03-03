from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
import pytz
from datetime import datetime, time
from config import Config
import database
import news_fetcher
import whatsapp_api
import os
import time as time_module

logger = logging.getLogger(__name__)

def in_broadcast_window():
    """Check if current IST time is at 9 AM"""
    ist = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(ist)
    return now.hour == Config.SCHEDULE_START_HOUR

def run_broadcast_logic(triggered_by='scheduler'):
    """Core broadcast function - used by both Auto and Manual"""
    logger.info(f"🎙️ BROADCAST STARTED ({triggered_by})")
    
    # Skip auto if outside 9 AM window
    if triggered_by == 'scheduler' and not in_broadcast_window():
        logger.info("⏰ Outside 9 AM window, skipping auto broadcast")
        return {"success": False, "message": "Outside scheduled window", "skipped": True}
    
    try:
        subscribers = database.get_active_subscribers()
        if not subscribers:
            return {"success": False, "message": "No subscribers", "sent": 0, "failed": 0}
        
        wa = whatsapp_api.WhatsAppCloudAPI()
        if not wa.test_connection():
            return {"success": False, "message": "WhatsApp API failed", "sent": 0, "failed": 0}
        
        # Download audio files (Both Hindi and English)
        audio_files = {}
        audio_durations = {}
        
        for lang in ["english", "hindi"]:
            logger.info(f"🔍 Fetching {lang} bulletin...")
            bulletins = news_fetcher.fetch_audio_bulletins(lang)
            
            if bulletins:
                local = news_fetcher.download_audio(bulletins[0])
                if local:
                    audio_files[lang] = local
                    audio_durations[lang] = bulletins[0].get('duration', 0)
                    logger.info(f"✅ {lang} audio ready: {local}")
                else:
                    logger.error(f"❌ Failed to download {lang} audio")
            else:
                logger.error(f"❌ No {lang} bulletins found")
        
        if len(audio_files) < 2:
            return {"success": False, "message": "Audio download failed", "sent": 0, "failed": 0}
        
        # Send loop
        sent, failed = 0, 0
        ist = database.get_ist_time()
        date_str = ist.strftime("%d-%m-%Y")
        time_str = ist.strftime("%I:%M %p IST")
        
        for sub in subscribers:
            phone = ''.join(filter(str.isdigit, str(sub['phone_number'])))
            if phone.startswith('0'): phone = phone[1:]
            if not phone.startswith('91'): phone = '91' + phone
            if len(phone) != 12: continue
            
            try:
                # Send header
                header = f"🎙️ *AIR Bulletin*\n📅 {date_str} | ⏰ {time_str}\n🇬🇧 English 👇"
                wa.send_text_message(phone, header)
                
                # Send English audio
                wa._send_audio_with_upload(phone, audio_files['english'], is_local_path=True)
                
                # Send Hindi separator
                wa.send_text_message(phone, "🇮🇳 Hindi 👇")
                
                # Send Hindi audio
                wa._send_audio_with_upload(phone, audio_files['hindi'], is_local_path=True)
                
                # Send footer
                wa.send_text_message(phone, "✅ Done!")
                
                sent += 1
                logger.info(f"✅ Sent to {phone}")
                
            except Exception as e:
                failed += 1
                logger.error(f"Failed {phone}: {e}")
            
            time_module.sleep(2)  # Rate limit
        
        # Cleanup downloaded files
        for path in audio_files.values():
            if os.path.exists(path): os.remove(path)
        
        # Log broadcast with durations
        database.log_broadcast(
            sent, failed, 
            "direct", "direct", 
            triggered_by,
            audio_durations.get('english', 0),
            audio_durations.get('hindi', 0)
        )
        
        logger.info(f"🏁 Complete: {sent} sent, {failed} failed")
        return {"success": True, "sent": sent, "failed": failed, "total": len(subscribers)}
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return {"success": False, "error": str(e), "sent": 0, "failed": 0}

def start_scheduler():
    """Start auto-scheduler (9 AM IST daily)"""
    scheduler = BackgroundScheduler(timezone=pytz.timezone(Config.TIMEZONE))
    
    # Schedule at 9 AM IST every day
    scheduler.add_job(
        func=run_broadcast_logic,
        trigger=CronTrigger(hour=Config.SCHEDULE_START_HOUR, minute=0),
        id='auto_broadcast_9am',
        kwargs={'triggered_by': 'scheduler'},
        replace_existing=True
    )
    
    # Also add interval trigger during window
    scheduler.add_job(
        func=run_broadcast_logic,
        trigger=IntervalTrigger(minutes=Config.SCHEDULE_INTERVAL_MINUTES),
        id='auto_broadcast_interval',
        kwargs={'triggered_by': 'scheduler'},
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"✅ Scheduler: 9 AM IST daily + Every {Config.SCHEDULE_INTERVAL_MINUTES} min")
    return scheduler

def stop_scheduler(sched):
    if sched: sched.shutdown()