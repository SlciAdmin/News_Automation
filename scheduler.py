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
import time as time_module

logger = logging.getLogger(__name__)

# ✅ ADD THIS FUNCTION BACK
def in_broadcast_window():
    """Check if current IST time is at 9 AM"""
    ist = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(ist)
    return now.hour == Config.SCHEDULE_START_HOUR

def run_broadcast_logic(triggered_by='scheduler'):
    """Core broadcast function - fetches 8-8:30 AM English news and sends at 9 AM"""
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
        
        # Fetch English morning news (from 8-8:30 AM)
        logger.info("🔍 Fetching English morning news (8:00-8:30 AM)...")
        bulletins = news_fetcher.fetch_audio_bulletins()
        
        if not bulletins["english"]:
            logger.error("❌ Failed to fetch English morning news")
            return {"success": False, "message": "No English news found", "sent": 0, "failed": 0}
        
        # Download English audio
        logger.info("⬇️ Downloading English audio...")
        english_path = news_fetcher.download_audio(bulletins["english"])
        
        if not english_path:
            logger.error("❌ Failed to download English audio")
            return {"success": False, "message": "English download failed", "sent": 0, "failed": 0}
        
        # Convert to Hindi or download Hindi version
        logger.info("🔄 Preparing Hindi audio...")
        hindi_path = None
        
        # Try to get/converthindi
        if bulletins["hindi"]:
            hindi_path = news_fetcher.download_audio(bulletins["hindi"])
        
        # If no Hindi version, convert English to Hindi
        if not hindi_path and english_path:
            logger.info("🎤 Converting English audio to Hindi...")
            hindi_path = news_fetcher.convert_audio_to_hindi(english_path)
        
        if not hindi_path:
            logger.error("❌ Failed to get Hindi audio")
            # Clean up English file
            if os.path.exists(english_path):
                os.remove(english_path)
            return {"success": False, "message": "Hindi audio failed", "sent": 0, "failed": 0}
        
        # Get durations
        english_duration = news_fetcher.get_audio_duration(english_path) or 0
        hindi_duration = news_fetcher.get_audio_duration(hindi_path) or 0
        
        # Send to subscribers
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
                # Send header with morning news info
                header = f"🎙️ *AIR Morning News*\n📅 {date_str} | ⏰ {time_str}\n🗣️ 8:00-8:30 AM Bulletin"
                wa.send_text_message(phone, header)
                
                # Send English audio
                wa._send_audio_with_upload(phone, english_path, is_local_path=True)
                
                # Brief pause
                time_module.sleep(1)
                
                # Send Hindi audio
                wa._send_audio_with_upload(phone, hindi_path, is_local_path=True)
                
                # Send footer
                wa.send_text_message(phone, "✅ Today's morning news delivered!")
                
                sent += 1
                logger.info(f"✅ Sent to {phone}")
                
            except Exception as e:
                failed += 1
                logger.error(f"Failed {phone}: {e}")
            
            time_module.sleep(2)  # Rate limit
        
        # Cleanup downloaded files
        for path in [english_path, hindi_path]:
            if path and os.path.exists(path):
                os.remove(path)
        
        # Log broadcast
        database.log_broadcast(
            sent, failed, 
            "morning_news", "morning_news_converted", 
            triggered_by,
            english_duration,
            hindi_duration
        )
        
        logger.info(f"🏁 Complete: {sent} sent, {failed} failed")
        return {"success": True, "sent": sent, "failed": failed, "total": len(subscribers)}
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}", exc_info=True)
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
    
    scheduler.start()
    logger.info(f"✅ Scheduler: Daily at {Config.SCHEDULE_START_HOUR}:00 AM IST")
    return scheduler

def stop_scheduler(sched):
    if sched:
        sched.shutdown()