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
    """Core broadcast function - fetches 7-7:30 AM news, sends at 9 AM"""
    logger.info(f"🎙️ BROADCAST STARTED ({triggered_by})")
    
    # ✅ Still check 9 AM window for sending
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
        
        # ✅ Fetch 7-7:30 AM news (both languages)
        logger.info("🔍 Fetching 7AM morning news (English + Hindi)...")
        bulletins = news_fetcher.fetch_audio_bulletins()
        
        if not bulletins["english"] and not bulletins["hindi"]:
            logger.error("❌ Failed to fetch any morning news")
            return {"success": False, "message": "No news found", "sent": 0, "failed": 0}
        
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
                # ✅ Send header
                header = f"🎙️ *AIR Morning News*\n📅 {date_str} | ⏰ {time_str}\n🗣️ 7:00-7:30 AM Bulletin"
                wa.send_text_message(phone, header)
                
                # ✅ Send English audio if available
                if bulletins["english"]:
                    eng_path = news_fetcher.download_audio(bulletins["english"])
                    if eng_path:
                        wa._send_audio_with_upload(phone, eng_path, is_local_path=True)
                        if os.path.exists(eng_path):
                            os.remove(eng_path)  # Cleanup
                
                time_module.sleep(1)  # Brief pause
                
                # ✅ Send Hindi audio if available
                if bulletins["hindi"]:
                    hindi_path = news_fetcher.download_audio(bulletins["hindi"])
                    if hindi_path:
                        wa._send_audio_with_upload(phone, hindi_path, is_local_path=True)
                        if os.path.exists(hindi_path):
                            os.remove(hindi_path)  # Cleanup
                
                # ✅ Send footer
                wa.send_text_message(phone, "✅ Today's 7AM news delivered!")
                sent += 1
                logger.info(f"✅ Sent to {phone}")
                
            except Exception as e:
                failed += 1
                logger.error(f"Failed {phone}: {e}")
            
            time_module.sleep(2)  # Rate limit
        
        # ✅ Log broadcast
        database.log_broadcast(
            sent, failed,
            "morning_news_7am_en", "morning_news_7am_hi",
            triggered_by
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