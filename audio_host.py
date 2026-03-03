import requests
import os
import logging
import time
from config import Config

logger = logging.getLogger(__name__)

# =============================================================================
# ✅ CRITICAL FIX: All API URLs have NO trailing spaces
# =============================================================================

# -----------------------------
# CATBOX UPLOAD
# -----------------------------
def upload_to_catbox(file_path, max_retries=3):
    """Upload file to catbox.moe"""
    for attempt in range(max_retries):
        try:
            filename = os.path.basename(file_path)

            with open(file_path, "rb") as f:
                files = {"fileToUpload": (filename, f, "audio/mpeg")}
                data = {"reqtype": "fileupload"}

                # ✅ FIXED: Removed trailing spaces from URL
                response = requests.post(
                    "https://catbox.moe/user/api.php",  # ← NO TRAILING SPACE
                    files=files,
                    data=data,
                    timeout=120
                )

            if response.status_code == 200:
                url = response.text.strip()
                if url.startswith("https://"):
                    logger.info(f"✅ Catbox upload success: {url}")
                    return url

            logger.warning(f"⚠️ Catbox upload failed (attempt {attempt+1}): {response.status_code}")

        except Exception as e:
            logger.warning(f"⚠️ Catbox error (attempt {attempt+1}): {e}")

        time.sleep(2 ** attempt)

    return None


# -----------------------------
# PIXELDRAIN UPLOAD
# -----------------------------
def upload_to_pixeldrain(file_path, max_retries=3):
    """Upload file to pixeldrain with longer timeout"""
    for attempt in range(max_retries):
        try:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            logger.info(f"📤 Uploading to pixeldrain ({file_size/1024/1024:.2f} MB) - attempt {attempt+1}")
            
            with open(file_path, "rb") as f:
                # ✅ FIXED: Removed trailing spaces from URL
                response = requests.post(
                    "https://pixeldrain.com/api/file",  # ← NO TRAILING SPACE
                    files={"file": (filename, f, "audio/mpeg")},
                    timeout=300,  # Increased to 5 minutes
                    headers={"User-Agent": "Mozilla/5.0"}
                )
            
            if response.status_code == 201:
                result = response.json()
                file_id = result.get("id")
                if file_id:
                    # ✅ FIXED: Removed space in URL construction
                    url = f"https://pixeldrain.com/u/{file_id}"  # ← NO SPACE BEFORE {file_id}
                    logger.info(f"✅ Pixeldrain upload success: {url}")
                    return url
            else:
                logger.warning(f"⚠️ Pixeldrain returned {response.status_code}: {response.text[:100]}")
                
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ Pixeldrain timeout (attempt {attempt+1})")
        except Exception as e:
            logger.warning(f"⚠️ Pixeldrain error: {e}")
        
        time.sleep(2 ** attempt)  # Exponential backoff
    
    return None


# -----------------------------
# FILE.IO UPLOAD (IMPROVED)
# -----------------------------
def upload_to_fileio(file_path, max_retries=3):
    """Upload file to file.io with better error handling"""
    for attempt in range(max_retries):
        try:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            logger.info(f"📤 Uploading to file.io ({file_size/1024/1024:.2f} MB) - attempt {attempt+1}")
            
            # file.io has a 100MB limit, we're well under that
            with open(file_path, "rb") as f:
                # ✅ FIXED: Removed trailing spaces from URL
                response = requests.post(
                    "https://file.io",  # ← NO TRAILING SPACE
                    files={"file": (filename, f, "audio/mpeg")},
                    data={
                        "expires": "1d",  # Expires in 1 day
                        "maxDownloads": 100,  # Allow up to 100 downloads
                        "autoDelete": False  # Don't auto-delete
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json"
                    },
                    timeout=120,  # 2 minute timeout
                    verify=True
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    url = result.get("link")
                    logger.info(f"✅ File.io upload success: {url}")
                    return url
                else:
                    logger.warning(f"⚠️ File.io returned error: {result.get('error', 'Unknown error')}")
            elif response.status_code == 429:
                logger.warning("⚠️ File.io rate limited (429), waiting before retry...")
                time.sleep(10)  # Wait 10 seconds if rate limited
            else:
                logger.warning(f"⚠️ File.io returned {response.status_code}: {response.text[:100]}")
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"⚠️ File.io connection error (attempt {attempt+1}): {e}")
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ File.io timeout (attempt {attempt+1})")
        except Exception as e:
            logger.warning(f"⚠️ File.io error: {e}")
        
        # Exponential backoff with longer waits
        wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
        logger.info(f"⏱️ Waiting {wait_time}s before retry...")
        time.sleep(wait_time)
    
    return None


# -----------------------------
# MAIN HOSTING FUNCTION
# -----------------------------
def host_audio_file(file_path):
    """Upload audio file using multiple services with better fallback order"""
    
    if not os.path.exists(file_path):
        logger.error(f"❌ File not found: {file_path}")
        return None
    
    filename = os.path.basename(file_path)
    logger.info(f"📤 Hosting audio: {filename}")
    
    # OWN SERVER OPTION
    if Config.AUDIO_HOST_SERVICE == "own_server" and Config.AUDIO_HOST_BASE_URL:
        url = f"{Config.AUDIO_HOST_BASE_URL.rstrip('/')}/{filename}"
        logger.info(f"✅ Using own server: {url}")
        return url
    
    # TRY DIFFERENT HOSTS IN ORDER (prioritizing file.io as it's most reliable)
    hosting_services = [
        ("file.io", upload_to_fileio),      # Try file.io first
        ("catbox", upload_to_catbox),       # Then catbox
        ("pixeldrain", upload_to_pixeldrain) # pixeldrain last
    ]
    
    for service_name, upload_func in hosting_services:
        logger.info(f"🔄 Trying {service_name}...")
        url = upload_func(file_path)
        if url:
            logger.info(f"✅ Success with {service_name}: {url}")
            return url
        logger.warning(f"⚠️ {service_name} failed, trying next...")
    
    logger.error("❌ All audio hosting methods failed")
    return None