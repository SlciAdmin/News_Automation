#!/usr/bin/env python3
"""Test direct WhatsApp sending with detailed logging"""
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
from whatsapp_api import WhatsAppCloudAPI

# Your test phone number (CHANGE THIS TO YOUR NUMBER)
TEST_PHONE = "919610608060"  # Replace with your number

def create_test_audio():
    """Create a small valid test audio file"""
    test_file = os.path.join(Config.AUDIO_DIR, "test_audio.mp3")
    
    # Create a simple MP3-like file (just for testing upload)
    # This is a minimal valid MP3 frame header
    with open(test_file, "wb") as f:
        # Write a valid MP3 frame header
        f.write(b'\xFF\xFB\x90\x00')  # MP3 frame sync
        f.write(b'\x00' * 1000)  # Padding
        
        # Add ID3 tag for better compatibility
        f.seek(0)
        f.write(b'ID3\x03\x00\x00\x00\x00\x00\x00')  # ID3v2 header
        
    return test_file

def test_text_message(wa):
    """Test sending a simple text message"""
    print("\n📝 Test 1: Sending text message...")
    success, result = wa.send_text_message(TEST_PHONE, "🧪 Test message from debug script")
    
    if success:
        print(f"✅ Text message sent successfully!")
        print(f"   Result: {result}")
    else:
        print(f"❌ Text message failed: {result}")
    
    return success

def test_audio_upload(wa):
    """Test uploading audio to WhatsApp"""
    print("\n📤 Test 2: Testing audio upload...")
    
    test_file = create_test_audio()
    print(f"   Test file created: {test_file} ({os.path.getsize(test_file)} bytes)")
    
    success, result = wa.upload_media_to_whatsapp(test_file)
    
    if success:
        print(f"✅ Upload successful!")
        print(f"   Media ID: {result}")
    else:
        print(f"❌ Upload failed: {result}")
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)
    
    return success, result if success else None

def test_full_audio_send(wa, media_id=None):
    """Test sending audio using media_id"""
    print("\n🎵 Test 3: Sending audio message...")
    
    if not media_id:
        # Create and upload a test file
        test_file = create_test_audio()
        success, media_id = wa.upload_media_to_whatsapp(test_file)
        if os.path.exists(test_file):
            os.remove(test_file)
        if not success:
            print(f"❌ Could not upload test audio: {media_id}")
            return False
    
    success, result = wa.send_audio_message(TEST_PHONE, media_id)
    
    if success:
        print(f"✅ Audio sent successfully!")
        print(f"   Result: {result}")
    else:
        print(f"❌ Audio send failed: {result}")
    
    return success

def test_direct_send(wa):
    """Test direct send using _send_audio_with_upload"""
    print("\n🔄 Test 4: Testing direct _send_audio_with_upload...")
    
    test_file = create_test_audio()
    
    success, result = wa._send_audio_with_upload(TEST_PHONE, test_file, is_local_path=True)
    
    if success:
        print(f"✅ Direct send successful!")
        print(f"   Result: {result}")
    else:
        print(f"❌ Direct send failed: {result}")
    
    if os.path.exists(test_file):
        os.remove(test_file)
    
    return success

def main():
    print("=" * 60)
    print("🔍 WHATSAPP API DIRECT TEST")
    print("=" * 60)
    
    print(f"\n📱 Testing with phone: {TEST_PHONE}")
    
    # Check configuration
    print("\n🔧 Configuration check:")
    print(f"   Phone ID: {Config.WHATSAPP_PHONE_NUMBER_ID}")
    print(f"   API Base: {Config.WHATSAPP_API_BASE}")
    print(f"   Token starts with: {Config.WHATSAPP_ACCESS_TOKEN[:20]}...")
    
    # Initialize API
    wa = WhatsAppCloudAPI()
    
    # Test connection first
    print("\n🔗 Testing API connection...")
    if wa.test_connection():
        print("✅ WhatsApp API connected successfully")
    else:
        print("❌ WhatsApp API connection failed")
        print("\n💡 Check your .env file:")
        print("   - WHATSAPP_PHONE_NUMBER_ID")
        print("   - WHATSAPP_ACCESS_TOKEN")
        print("   - WHATSAPP_API_BASE (should be https://graph.facebook.com/v19.0)")
        return
    
    # Run tests
    test_text_message(wa)
    time.sleep(2)
    
    success, media_id = test_audio_upload(wa)
    time.sleep(2)
    
    if success:
        test_full_audio_send(wa, media_id)
        time.sleep(2)
    
    test_direct_send(wa)
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()