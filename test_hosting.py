#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.INFO)

from audio_host import upload_to_pixeldrain, upload_to_fileio, upload_to_catbox

# Create a small test file
test_file = "test_audio.mp3"
with open(test_file, "wb") as f:
    # Create a small dummy MP3 file
    f.write(b'\xFF\xFB\x90\x00' + b'\x00' * 10000)  # 10KB dummy MP3

print("🔍 Testing audio hosting services...")
print("-" * 50)

# Test pixeldrain
print("📤 Testing pixeldrain...")
url = upload_to_pixeldrain(test_file)
if url:
    print(f"✅ pixeldrain SUCCESS: {url}")
else:
    print("❌ pixeldrain FAILED")

print("-" * 50)

# Test file.io
print("📤 Testing file.io...")
url = upload_to_fileio(test_file)
if url:
    print(f"✅ file.io SUCCESS: {url}")
else:
    print("❌ file.io FAILED")

print("-" * 50)

# Test catbox
print("📤 Testing catbox...")
url = upload_to_catbox(test_file)
if url:
    print(f"✅ catbox SUCCESS: {url}")
else:
    print("❌ catbox FAILED")

# Cleanup
os.remove(test_file)
print("-" * 50)
print("Test complete!")