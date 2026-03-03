#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.INFO)

from audio_host import upload_to_fileio

# Create a small test file
test_file = "test_audio.mp3"
with open(test_file, "wb") as f:
    # Create a 50KB dummy MP3 file
    f.write(b'\xFF\xFB\x90\x00' + b'\x00' * 50000)

print("🔍 Testing file.io hosting...")
print("-" * 50)

# Test file.io
url = upload_to_fileio(test_file)
if url:
    print(f"✅ file.io SUCCESS: {url}")
    
    # Test if the URL is accessible
    import requests
    print("\n🔍 Testing URL accessibility...")
    try:
        r = requests.head(url, timeout=10)
        if r.status_code == 200:
            print("✅ URL is accessible!")
        else:
            print(f"⚠️ URL returned status: {r.status_code}")
    except Exception as e:
        print(f"❌ URL test failed: {e}")
else:
    print("❌ file.io FAILED")

# Cleanup
os.remove(test_file)
print("-" * 50)
print("Test complete!")