#!/usr/bin/env python3
"""Test script to verify WhatsApp API fix"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from whatsapp_api import WhatsAppCloudAPI

print("🔍 Testing Configuration...")
print(f"API Base: '{Config.WHATSAPP_API_BASE}' (length: {len(Config.WHATSAPP_API_BASE)})")
print(f"Phone ID: '{Config.WHATSAPP_PHONE_NUMBER_ID}'")
print(f"Token starts with: '{Config.WHATSAPP_ACCESS_TOKEN[:20]}...'")

# Check for trailing spaces
if Config.WHATSAPP_API_BASE != Config.WHATSAPP_API_BASE.strip():
    print("❌ ERROR: WHATSAPP_API_BASE has trailing/leading spaces!")
    sys.exit(1)
else:
    print("✅ API Base URL is clean")

print("\n🔗 Testing WhatsApp Connection...")
wa = WhatsAppCloudAPI()
if wa.test_connection():
    print("✅ Connection successful!")
else:
    print("❌ Connection failed - check token permissions")

print("\n🎵 Testing Media Upload (small test file)...")
# Create a tiny dummy MP3 for testing
test_file = os.path.join(Config.AUDIO_DIR, "test_dummy.mp3")
with open(test_file, "wb") as f:
    # Minimal valid MP3 header (not real audio, just for API test)
    f.write(b'\xff\xfb\x90\x00' + b'\x00' * 100)

success, result = wa.upload_media_to_whatsapp(test_file)
print(f"Upload result: success={success}, result={result}")

# Cleanup
if os.path.exists(test_file):
    os.remove(test_file)

print("\n✅ Test complete!")