from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import pytz
from datetime import datetime
from config import Config
import database
import news_fetcher
import whatsapp_api
from tts_engine import TTSEngine
import os
import time as time_module

logger = logging.getLogger(__name__)

def in_broadcast_window():
    ist = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(ist)
    return Config.SCHEDULE_START_HOUR <= now.hour < Config.SCHEDULE_END_HOUR

def run_headlines_tts_broadcast(triggered_by='scheduler'):
    """
    ✅ CORE: Fetch REAL headlines → TTS (EN+HI) → WhatsApp AUDIO ONLY
    """
    logger.info(f"🎙️ HEADLINES TTS BROADCAST STARTED ({triggered_by})")
    
    try:
        # 1. Get subscribers
        subscribers = database.get_active_subscribers()
        if not subscribers:
            logger.warning("⚠️ No active subscribers found")
            return {"success": False, "message": "No subscribers", "sent": 0, "failed": 0}
        
        # 2. Test WhatsApp connection
        logger.info("🔌 Testing WhatsApp API connection...")
        wa = whatsapp_api.WhatsAppCloudAPI()
        if not wa.test_connection():
            logger.error("❌ WhatsApp API connection FAILED")
            return {"success": False, "message": "WhatsApp API failed", "sent": 0, "failed": 0}
        logger.info("✅ WhatsApp API connected")
        
        # 3. ✅ Fetch REAL headlines from website (NO DUMMY)
        logger.info("🔍 Fetching REAL headlines from newsonair.gov.in...")
        news_data = news_fetcher.fetch_morning_headlines()
        
        # ✅ MERGED: Better error handling with actual error message
        if not news_data.get('success') or not news_data.get('headlines'):
            error_msg = news_data.get('error', 'Unknown error')
            logger.error(f"❌ Failed to fetch headlines: {error_msg}")
            return {
                "success": False, 
                "message": f"Could not fetch headlines: {error_msg}", 
                "sent": 0, 
                "failed": 0,
                "error_details": error_msg
            }
        
        headlines = news_data['headlines'][:6]  # Ensure max 6
        logger.info(f"✅ Got {len(headlines)} REAL headlines")
        for i, hl in enumerate(headlines, 1):
            logger.info(f"   {i}. {hl[:70]}...")
        
        # 4. ✅ Generate TTS (English + Hindi)
        logger.info("🎤 Generating human-like TTS...")
        tts = TTSEngine()
        audio_paths = tts.generate_both_languages(headlines)
        
        if not audio_paths:
            logger.error("❌ TTS generation failed - no audio files created")
            return {"success": False, "message": "TTS generation failed", "sent": 0, "failed": 0}
        
        logger.info(f"✅ TTS generated: {list(audio_paths.keys())}")
        
        # 5. ✅ Send via WhatsApp - DIRECT AUDIO FILES (NO hosting needed)
        sent, failed = 0, 0
        ist = database.get_ist_time()
        date_str = ist.strftime("%d %b %Y")
        
        for sub in subscribers:
            phone = ''.join(filter(str.isdigit, str(sub['phone_number'])))
            if phone.startswith('0'): phone = phone[1:]
            if not phone.startswith('91'): phone = '91' + phone
            if len(phone) != 12:
                logger.warning(f"⚠️ Invalid phone format: {sub['phone_number']}")
                continue
            
            try:
                # ✅ Send English audio DIRECTLY
                if 'en' in audio_paths:
                    en_path = audio_paths['en']
                    if os.path.exists(en_path):
                        success, result = wa.send_audio_file_direct(phone, en_path)
                        if success:
                            logger.info(f"✅ EN audio sent to {phone}")
                        else:
                            logger.warning(f"⚠️ EN audio failed for {phone}: {result}")
                        time_module.sleep(2)
                    else:
                        logger.warning(f"⚠️ EN audio file not found: {en_path}")
                
                # ✅ Send Hindi audio DIRECTLY
                if 'hi' in audio_paths:
                    hi_path = audio_paths['hi']
                    if os.path.exists(hi_path):
                        success, result = wa.send_audio_file_direct(phone, hi_path)
                        if success:
                            logger.info(f"✅ HI audio sent to {phone}")
                        else:
                            logger.warning(f"⚠️ HI audio failed for {phone}: {result}")
                        time_module.sleep(2)
                    else:
                        logger.warning(f"⚠️ HI audio file not found: {hi_path}")
                
                sent += 1
                logger.info(f"✅ Sent to {phone}")
                
            except Exception as e:
                failed += 1
                logger.error(f"❌ Failed to send to {phone}: {e}", exc_info=True)
            
            time_module.sleep(2)  # Rate limit between subscribers
        
        # ✅ Cleanup local TTS files
        for lang, path in audio_paths.items():
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug(f"🗑️ Cleaned up {lang}: {path}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete {path}: {e}")
        
        # ✅ Log broadcast results
        database.log_broadcast(
            sent=sent, 
            failed=failed,
            en_url="AUDIO_SENT_DIRECT_EN",
            hi_url="AUDIO_SENT_DIRECT_HI",
            triggered_by=triggered_by,
            en_duration=len(headlines) * 12,
            hi_duration=len(headlines) * 15
        )
        
        logger.info(f"🏁 Broadcast Complete: {sent} sent, {failed} failed")
        return {
            "success": True, 
            "sent": sent, 
            "failed": failed,
            "total": len(subscribers),
            "headlines_count": len(headlines),
            "languages": list(audio_paths.keys())
        }
        
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "sent": 0, "failed": 0}

# Backward compatibility
def run_broadcast_logic(triggered_by='scheduler'):
    return run_headlines_tts_broadcast(triggered_by)

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone(Config.TIMEZONE))
    scheduler.add_job(
        func=run_headlines_tts_broadcast,
        trigger=CronTrigger(hour=Config.SCHEDULE_START_HOUR, minute=0),
        id='headlines_9am',
        kwargs={'triggered_by': 'scheduler'},
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"✅ Scheduler: Daily {Config.SCHEDULE_START_HOUR}:00 AM IST")
    return scheduler

def stop_scheduler(sched):
    if sched and getattr(sched, 'running', False):
        sched.shutdown(wait=True)
        logger.info("🛑 Scheduler stopped")