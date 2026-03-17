import requests
import os
import logging
import time
from config import Config

logger = logging.getLogger(__name__)

def upload_to_catbox(file_path, max_retries=3):
    """✅ Upload to catbox.moe (Most reliable for audio files)"""
    for attempt in range(max_retries):
        try:
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"fileToUpload": (filename, f, "audio/mpeg")}
                data = {"reqtype": "fileupload"}
                
                response = requests.post(
                    "https://catbox.moe/user/api.php",  # ✅ NO trailing space
                    files=files,
                    data=data,
                    timeout=120,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
            
            if response.status_code == 200:
                url = response.text.strip()
                if url.startswith("https://") and "catbox" in url:
                    logger.info(f"✅ Catbox upload success: {url}")
                    return url
            
            logger.warning(f"⚠️ Catbox attempt {attempt+1} failed: {response.status_code}")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"⚠️ Catbox error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None

def upload_to_fileio(file_path, max_retries=2):
    """✅ Fallback to file.io with proper headers"""
    for attempt in range(max_retries):
        try:
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                response = requests.post(
                    "https://file.io",
                    files={"file": (filename, f, "audio/mpeg")},
                    data={"expires": "1d"},
                    timeout=120,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json"
                    }
                )
            
            try:
                result = response.json()
                if response.status_code == 200 and result.get("success"):
                    url = result.get("link")
                    if url and url.startswith("https://"):
                        logger.info(f"✅ File.io upload: {url}")
                        return url
            except:
                pass
            time.sleep(5)
        except Exception as e:
            logger.warning(f"⚠️ File.io error: {e}")
            time.sleep(5)
    return None

def host_audio_file(file_path):
    """✅ Upload audio: catbox first, then file.io"""
    if not os.path.exists(file_path):
        logger.error(f"❌ File not found: {file_path}")
        return None
    
    filename = os.path.basename(file_path)
    logger.info(f"📤 Hosting: {filename} ({os.path.getsize(file_path)/1024:.1f} KB)")
    
    # Try catbox FIRST (most reliable)
    url = upload_to_catbox(file_path)
    if url: return url
    
    # Fallback to file.io
    url = upload_to_fileio(file_path)
    if url: return url
    
    logger.error("❌ All hosting failed")
    return None