#!/usr/bin/env python3
"""Debug the complete broadcast flow step by step"""
import os
import sys
import logging
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from config import Config
import database
import news_fetcher
import whatsapp_api

# Your test phone number
TEST_PHONE = "919610608060"

def debug_broadcast_flow():
    """Test each step of the broadcast process"""
    print("=" * 60)
    print("🔍 DEBUGGING BROADCAST FLOW")
    print("=" * 60)
    
    # Step 1: Check database
    print("\n📋 Step 1: Checking database...")
    subscribers = database.get_active_subscribers()
    print(f"   Active subscribers: {len(subscribers)}")
    for sub in subscribers:
        print(f"   - {sub['phone_number']} ({sub['language_pref']})")
    
    if not subscribers:
        print("   ❌ No subscribers found! Add a subscriber first.")
        return
    
    # Step 2: Test WhatsApp connection
    print("\n🔗 Step 2: Testing WhatsApp connection...")
    wa = whatsapp_api.WhatsAppCloudAPI()
    if wa.test_connection():
        print("   ✅ WhatsApp API connected")
    else:
        print("   ❌ WhatsApp API connection failed")
        return
    
    # Step 3: Fetch bulletins
    print("\n📰 Step 3: Fetching bulletins...")
    audio_files = {}
    
    for lang in ["english", "hindi"]:
        print(f"\n   🔍 Fetching {lang} bulletin...")
        bulletins = news_fetcher.fetch_audio_bulletins(lang)
        if not bulletins:
            print(f"   ❌ No {lang} bulletins found")
            continue
        
        print(f"   ✅ Found {lang} bulletin: {bulletins[0]['url']}")
        
        # Step 4: Download audio
        print(f"   ⬇️ Downloading {lang} audio...")
        local_audio = news_fetcher.download_audio(bulletins[0])
        
        if not local_audio:
            print(f"   ❌ Failed to download {lang} audio")
            continue
        
        print(f"   ✅ Downloaded: {local_audio} ({os.path.getsize(local_audio)} bytes)")
        audio_files[lang] = local_audio
    
    # Check if both languages are ready
    if "english" not in audio_files or "hindi" not in audio_files:
        missing = [lang for lang in ["english", "hindi"] if lang not in audio_files]
        print(f"\n❌ Missing audio files: {missing}")
        return
    
    print("\n✅ Both audio files downloaded successfully!")
    
    # Step 5: Send test broadcast to YOUR number only
    print("\n📤 Step 5: Sending test broadcast to YOUR number...")
    
    # Get current time
    from datetime import datetime
    import pytz
    ist = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(ist)
    date_str = now.strftime("%d-%m-%Y")
    time_str = now.strftime("%I:%M %p IST")
    
    try:
        # Send header
        print("   Sending header text...")
        header = (
            f"🎙️ *All India Radio - National Bulletin* (TEST)\n"
            f"📅 {date_str} | ⏰ {time_str}\n\n"
            f"🇬🇧 English bulletin test...👇"
        )
        success, result = wa.send_text_message(TEST_PHONE, header)
        print(f"   Header sent: {'✅' if success else '❌'}")
        time.sleep(2)
        
        # Send English audio
        print("   Sending English audio...")
        en_success, en_result = wa._send_audio_with_upload(TEST_PHONE, audio_files["english"], is_local_path=True)
        print(f"   English audio: {'✅' if en_success else '❌'}")
        if not en_success:
            print(f"   Error: {en_result}")
        time.sleep(2)
        
        # Send Hindi separator
        print("   Sending Hindi separator...")
        wa.send_text_message(TEST_PHONE, "🇮🇳 Hindi bulletin test (हिंदी) starting...👇")
        time.sleep(2)
        
        # Send Hindi audio
        print("   Sending Hindi audio...")
        hi_success, hi_result = wa._send_audio_with_upload(TEST_PHONE, audio_files["hindi"], is_local_path=True)
        print(f"   Hindi audio: {'✅' if hi_success else '❌'}")
        if not hi_success:
            print(f"   Error: {hi_result}")
        time.sleep(1)
        
        # Send footer
        wa.send_text_message(TEST_PHONE, "✅ Test broadcast complete!")
        
        if en_success or hi_success:
            print("\n✅ Test broadcast sent successfully!")
        else:
            print("\n❌ Test broadcast failed - both audio sends failed")
            
    except Exception as e:
        print(f"\n❌ Exception during send: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    print("\n🧹 Cleaning up downloaded files...")
    for lang, file_path in audio_files.items():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"   Removed: {file_path}")
        except Exception as e:
            print(f"   Error removing {file_path}: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Debug complete!")
    print("=" * 60)

if __name__ == "__main__":
    debug_broadcast_flow()