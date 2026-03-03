#!/usr/bin/env python3
"""Debug script to test each broadcast component"""
import os, sys, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)

from config import Config
import database
import news_fetcher
import audio_host
import whatsapp_api

print("🔍 ===== BROADCAST DEBUG START =====\n")

# 1️⃣ Check database subscribers
print("📋 1. Checking subscribers...")
database.init_db()
subs = database.get_active_subscribers()
print(f"   Active subscribers: {len(subs)}")
if subs:
    for s in subs:
        print(f"   → {s['phone_number']} ({s['language_pref']})")
else:
    print("   ❌ NO SUBSCRIBERS FOUND - Add one first!")
    print("   Try: POST /api/subscriber with {\"phone_number\": \"919610608060\"}")

# 2️⃣ Test WhatsApp connection
print("\n🔗 2. Testing WhatsApp API...")
wa = whatsapp_api.WhatsAppCloudAPI()
if wa.test_connection():
    print("   ✅ WhatsApp API connected")
else:
    print("   ❌ WhatsApp API connection FAILED")
    print(f"   Check: Token valid? Phone number verified? Permissions granted?")

# 3️⃣ Test news fetching
print("\n📰 3. Testing news fetch (English)...")
bulletins_en = news_fetcher.fetch_audio_bulletins("english")
if bulletins_en:
    print(f"   ✅ Found: {bulletins_en[0]['url']}")
else:
    print("   ❌ No English bulletins found")
    print("   Check: NEWS_SOURCE_URL accessible? Website structure changed?")

print("\n📰 4. Testing news fetch (Hindi)...")
bulletins_hi = news_fetcher.fetch_audio_bulletins("hindi")
if bulletins_hi:
    print(f"   ✅ Found: {bulletins_hi[0]['url']}")
else:
    print("   ❌ No Hindi bulletins found")

# 4️⃣ Test audio download + hosting
if bulletins_en:
    print("\n⬇️ 5. Testing audio download...")
    local = news_fetcher.download_audio(bulletins_en[0])
    if local:
        print(f"   ✅ Downloaded: {local} ({os.path.getsize(local)} bytes)")
        
        print("\n☁️ 6. Testing audio hosting...")
        public = audio_host.host_audio_file(local)
        if public:
            print(f"   ✅ Hosted: {public}")
        else:
            print("   ❌ Hosting failed")
    else:
        print("   ❌ Download failed")

# 5️⃣ Test direct WhatsApp send (if we have a public URL)
if bulletins_en and len(subs) > 0:
    print(f"\n📤 7. Testing direct send to {subs[0]['phone_number']}...")
    test_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"  # Public test MP3
    
    # Quick test: send text first
    success, result = wa.send_text_message(
        str(subs[0]['phone_number']).replace("+", ""),
        "🧪 Test message from debug script"
    )
    if success:
        print("   ✅ Text message sent successfully!")
        print("   👉 Check your WhatsApp now for the test message")
    else:
        print(f"   ❌ Text send failed: {result}")
        print("   Possible causes:")
        print("   • User hasn't messaged your business in last 24h (session message rule)")
        print("   • Phone number not opted-in to your WhatsApp Business account")
        print("   • Token lacks 'whatsapp_business_messaging' permission")

print("\n🔍 ===== DEBUG COMPLETE =====")
print("\n💡 Next steps:")
print("1. If NO SUBSCRIBERS: Add your number via POST /api/subscriber")
print("2. If WHATSAPP FAILED: Check Meta Developer Portal permissions")
print("3. If NO BULLETINS: Check if newsonair.gov.in structure changed")
print("4. If SEND FAILED: Ensure user messaged your business first (24h rule)")