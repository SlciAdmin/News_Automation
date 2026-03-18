# scheduler.py - ✅ COMPLETE MERGED VERSION
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
    """Check if current time is within broadcast window"""
    ist = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(ist)
    return Config.SCHEDULE_START_HOUR <= now.hour < Config.SCHEDULE_END_HOUR

def run_headlines_tts_broadcast(triggered_by='scheduler'):
    """
    ✅ CORE: Fetch ALL 6 REAL headlines → TTS (EN+HI) → WhatsApp with EXACT FORMAT
    """
    logger.info(f"🎙️ HEADLINES TTS BROADCAST STARTED ({triggered_by})")
    
    try:
        # 1. ✅ Get active subscribers
        subscribers = database.get_active_subscribers()
        if not subscribers:
            logger.warning("⚠️ No active subscribers found")
            return {"success": False, "message": "No subscribers", "sent": 0, "failed": 0}
        
        logger.info(f"👥 Found {len(subscribers)} active subscribers")
        
        # 2. ✅ Test WhatsApp connection
        logger.info("🔌 Testing WhatsApp API connection...")
        wa = whatsapp_api.WhatsAppCloudAPI()
        if not wa.test_connection():
            logger.error("❌ WhatsApp API connection FAILED")
            return {"success": False, "message": "WhatsApp API failed", "sent": 0, "failed": 0}
        logger.info("✅ WhatsApp API connected")
        
        # 3. ✅✅✅ FETCH ALL 6 REAL HEADLINES
        logger.info("🔍 Fetching ALL 6 headlines from newsonair.gov.in...")
        news_data = news_fetcher.fetch_morning_headlines()
        
        # ✅ Enhanced error handling with debug info
        if not news_data.get('success'):
            error_msg = news_data.get('error', 'Unknown error')
            logger.error(f"❌ Failed to fetch headlines: {error_msg}")
            return {
                "success": False,
                "message": f"Could not fetch headlines: {error_msg}",
                "sent": 0,
                "failed": 0,
                "error_details": error_msg,
                "debug_hint": "Check if website structure changed or network issue"
            }
        
        # ✅ Get headlines and validate count
        headlines = news_data.get('headlines', [])
        
        if not headlines:
            logger.error("❌ No headlines extracted - website may have changed")
            return {
                "success": False,
                "message": "No headlines could be extracted",
                "sent": 0,
                "failed": 0,
                "debug_hint": "Check news_fetcher.py regex patterns"
            }
        
        # ⚠️ Warning if less than 6, but still proceed
        if len(headlines) < 6:
            logger.warning(f"⚠️ Only got {len(headlines)} headlines (expected 6) - proceeding anyway")
        else:
            logger.info(f"✅ Perfect! Got all {len(headlines)} headlines")
        
        # ✅ Log each headline for verification
        logger.info(f"✅ Got {len(headlines)} headlines:")
        for i, hl in enumerate(headlines, 1):
            logger.info(f"   📰 {i}. {hl}")
        
        # 4. ✅ Generate TTS in BOTH languages (English + Hindi)
        logger.info("🎤 Generating human-like TTS audio (English + Hindi)...")
        tts = TTSEngine()
        audio_paths = tts.generate_both_languages(headlines)
        
        if not audio_paths:
            logger.error("❌ TTS generation failed - no audio files created")
            return {"success": False, "message": "TTS generation failed", "sent": 0, "failed": 0}
        
        logger.info(f"✅ TTS audio files generated: {list(audio_paths.keys())}")
        for lang, path in audio_paths.items():
            size_kb = os.path.getsize(path) / 1024 if os.path.exists(path) else 0
            logger.info(f"   🎵 {lang.upper()}: {os.path.basename(path)} ({size_kb:.1f} KB)")
        
        # 5. ✅✅✅ Send via WhatsApp with EXACT FORMAT REQUESTED
        sent, failed = 0, 0
        failed_phones = []
        ist = database.get_ist_time()
        
        # ✅ Format date and time for both languages
        date_en = ist.strftime("%d %B %Y")           # 18 March 2026
        time_en = ist.strftime("%I:%M %p")            # 10:00 AM
        day_en = ist.strftime("%A")                   # Wednesday

        date_hi = ist.strftime("%d %B %Y")            # Same date
        time_hi = ist.strftime("%I:%M %p")
        
        # Hindi day name mapping
        day_hi_map = {
            'Monday': 'सोमवार', 'Tuesday': 'मंगलवार', 'Wednesday': 'बुधवार',
            'Thursday': 'गुरुवार', 'Friday': 'शुक्रवार', 'Saturday': 'शनिवार', 'Sunday': 'रविवार'
        }
        day_hi = day_hi_map.get(day_en, day_en)

        # Hindi time conversion (AM/PM → पूर्वाह्न/अपराह्न)
        time_parts = time_en.split()
        time_num = time_parts[0]
        time_period = "पूर्वाह्न" if time_parts[1].upper() == "AM" else "अपराह्न"
        time_hi_formatted = f"{time_num} {time_period}"

        logger.info(f"📤 Starting WhatsApp broadcast to {len(subscribers)} subscribers...")

        for sub in subscribers:
            # ✅ Clean and format phone number
            phone = ''.join(filter(str.isdigit, str(sub['phone_number'])))
            if phone.startswith('0'): 
                phone = phone[1:]
            if not phone.startswith('91'): 
                phone = '91' + phone
            
            if len(phone) != 12:
                logger.warning(f"⚠️ Invalid phone format: {sub['phone_number']}")
                failed += 1
                failed_phones.append(sub['phone_number'])
                continue
            
            try:
                # ==================== 🇬🇧 ENGLISH SECTION ====================
                
                # ✅ Step 1: English Greeting Text
                en_greeting = f"""🙏 Jai Ram Ji! Good Morning

📅 Date: {date_en}
⏰ Time: {time_en}
📰 AIR Morning News - {day_en}

🎧 Today's Top {len(headlines)} Headlines in English"""
                
                success, _ = wa.send_text(phone, en_greeting)
                if success:
                    logger.info(f"✅ English greeting sent to {phone}")
                time_module.sleep(1)
                
                # ✅ Step 2: Send English Audio
                if 'en' in audio_paths:
                    en_path = audio_paths['en']
                    if os.path.exists(en_path):
                        success, result = wa.send_audio_file_direct(phone, en_path)
                        if success:
                            logger.info(f"✅ EN audio sent to {phone}")
                        else:
                            logger.warning(f"⚠️ EN audio failed for {phone}: {result}")
                    else:
                        logger.warning(f"⚠️ EN audio file not found: {en_path}")
                
                time_module.sleep(2)  # Gap between languages
                
                # ==================== 🇮🇳 HINDI SECTION ====================
                
                # ✅ Step 3: Hindi Greeting Text
                hi_greeting = f"""🙏 जय राम जी! शुभ प्रभात

📅 तिथि: {date_hi}
⏰ समय: {time_hi_formatted}
📰 एआईआर मॉर्निंग न्यूज़ - {day_hi}

🎧 आज की {len(headlines)} प्रमुख सुर्खियाँ हिंदी में"""
                
                success, _ = wa.send_text(phone, hi_greeting)
                if success:
                    logger.info(f"✅ Hindi greeting sent to {phone}")
                time_module.sleep(1)
                
                # ✅ Step 4: Send Hindi Audio
                if 'hi' in audio_paths:
                    hi_path = audio_paths['hi']
                    if os.path.exists(hi_path):
                        success, result = wa.send_audio_file_direct(phone, hi_path)
                        if success:
                            logger.info(f"✅ HI audio sent to {phone}")
                        else:
                            logger.warning(f"⚠️ HI audio failed for {phone}: {result}")
                    else:
                        logger.warning(f"⚠️ HI audio file not found: {hi_path}")
                
                time_module.sleep(1)
                
                # ✅ Step 5: Final Closing Message (Both Languages)
                closing_msg = "✨ Have a nice day! 🌞\n\nधन्यवाद! आपका दिन शुभ हो। 🙏"
                success, _ = wa.send_text(phone, closing_msg)
                if success:
                    logger.info(f"✅ Closing message sent to {phone}")
                
                sent += 1
                logger.info(f"✅ Completed sending to {phone} | Progress: {sent}/{len(subscribers)}")
                
            except Exception as e:
                failed += 1
                failed_phones.append(phone)
                logger.error(f"❌ Failed to send to {phone}: {e}", exc_info=True)
            
            # ✅ Rate limit between subscribers (avoid WhatsApp bans)
            time_module.sleep(2)
        
        # ✅ Cleanup local TTS files after broadcast
        for lang, path in audio_paths.items():
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug(f"🗑️ Cleaned up {lang}: {path}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete {path}: {e}")
        
        # ✅ Log broadcast results to database
        database.log_broadcast(
            sent=sent, 
            failed=failed,
            en_url="AUDIO_SENT_DIRECT_EN",
            hi_url="AUDIO_SENT_DIRECT_HI",
            triggered_by=triggered_by,
            en_duration=len(headlines) * 12,
            hi_duration=len(headlines) * 15
        )
        
        # ✅ Final summary
        logger.info(f"🏁 Broadcast Complete: {sent} sent, {failed} failed out of {len(subscribers)}")
        
        if failed_phones:
            logger.warning(f"⚠️ Failed phones: {failed_phones[:10]}{'...' if len(failed_phones) > 10 else ''}")
        
        return {
            "success": True, 
            "sent": sent, 
            "failed": failed,
            "total": len(subscribers),
            "headlines_count": len(headlines),
            "languages": list(audio_paths.keys()),
            "timestamp": ist.isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "sent": 0, "failed": 0}


# Backward compatibility alias
def run_broadcast_logic(triggered_by='scheduler'):
    return run_headlines_tts_broadcast(triggered_by)


def start_scheduler():
    """Initialize and start the APScheduler"""
    scheduler = BackgroundScheduler(timezone=pytz.timezone(Config.TIMEZONE))
    
    # Schedule daily broadcast at configured hour (e.g., 9:00 AM IST)
    scheduler.add_job(
        func=run_headlines_tts_broadcast,
        trigger=CronTrigger(hour=Config.SCHEDULE_START_HOUR, minute=0),
        id='headlines_daily_broadcast',
        kwargs={'triggered_by': 'scheduler'},
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"✅ Scheduler started: Daily {Config.SCHEDULE_START_HOUR}:00 AM IST")
    
    return scheduler


def stop_scheduler(sched):
    """Gracefully stop the scheduler"""
    if sched and getattr(sched, 'running', False):
        sched.shutdown(wait=True)
        logger.info("🛑 Scheduler stopped")