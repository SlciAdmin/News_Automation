import requests
from bs4 import BeautifulSoup
import os
import logging
import re
import time
import ssl
from datetime import datetime, timedelta
import pytz
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import mutagen
from mutagen.mp3 import MP3
import subprocess
import tempfile
import shutil

logger = logging.getLogger(__name__)

# -----------------------------
# SESSION WITH RETRY STRATEGY
# -----------------------------
def create_session():
    """Create requests session with automatic retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504, 104, 10054, 10060],
        allowed_methods=["GET", "HEAD", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

_session = None

def get_session():
    """Get or create global session"""
    global _session
    if _session is None:
        _session = create_session()
    return _session

def get_ist_time():
    """Get current time in configured timezone"""
    return datetime.now(pytz.timezone(Config.TIMEZONE))

# -----------------------------
# HELPER: Resolve Final URL (MISSING FUNCTION - ADD THIS)
# -----------------------------
def resolve_final_url(url, session=None):
    """Follow redirects and return the final working URL"""
    if session is None:
        session = get_session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = session.head(url, headers=headers, timeout=15, allow_redirects=True, verify=True)
        if resp.status_code in [200, 302, 301]:
            return resp.url
        resp = session.get(url, headers=headers, timeout=15, stream=True, allow_redirects=True, verify=True)
        return resp.url
    except Exception as e:
        logger.warning(f"⚠️ Could not resolve URL {url}: {e}")
        return url

# -----------------------------
# AUDIO DURATION VALIDATION
# -----------------------------
def get_audio_duration(file_path):
    """Get audio duration in seconds using mutagen"""
    try:
        audio = MP3(file_path)
        duration = audio.info.length
        logger.info(f"🎵 Audio duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        return duration
    except Exception as e:
        logger.warning(f"⚠️ Could not get duration: {e}")
        return None

def validate_audio_duration(file_path):
    """Check if audio duration is between 4-5 minutes (240-300 seconds)"""
    duration = get_audio_duration(file_path)
    if duration is None:
        logger.warning("⚠️ Could not validate duration - accepting file")
        return True, duration
    
    min_dur = Config.MIN_AUDIO_DURATION_SECONDS
    max_dur = Config.MAX_AUDIO_DURATION_SECONDS
    
    if min_dur <= duration <= max_dur:
        logger.info(f"✅ Duration valid: {duration:.2f}s (required: {min_dur}-{max_dur}s)")
        return True, duration
    else:
        logger.warning(f"⚠️ Duration out of range: {duration:.2f}s (required: {min_dur}-{max_dur}s)")
        
        # If auto-trim is enabled and duration is longer than max, we can trim it
        if Config.AUTO_TRIM_AUDIO and duration > max_dur:
            logger.info(f"✂️ Will trim audio from {duration:.2f}s to {max_dur}s")
            return True, duration  # Will be trimmed later
        # If allow longer is enabled, accept anyway
        elif Config.ALLOW_LONGER_AUDIO:
            logger.info(f"⚠️ Accepting longer audio (ALLOW_LONGER_AUDIO=true)")
            return True, duration
        else:
            return False, duration

def trim_audio_to_duration(input_path, max_duration=300):
    """Trim audio to max duration using FFmpeg"""
    try:
        # Check if FFmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except:
            logger.error("❌ FFmpeg not installed. Cannot trim audio.")
            return input_path
        
        # Create output path
        output_path = input_path.replace('.mp3', f'_trimmed_{max_duration}s.mp3')
        if output_path == input_path:
            output_path = input_path.replace('.mp3', '') + f'_trimmed_{max_duration}s.mp3'
        
        # Trim audio to max_duration seconds
        cmd = [
            'ffmpeg', '-i', input_path,
            '-t', str(max_duration),
            '-c', 'copy',
            '-y',  # Overwrite output file
            output_path
        ]
        
        logger.info(f"✂️ Trimming audio to {max_duration}s...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"✅ Audio trimmed successfully: {output_path}")
            return output_path
        else:
            logger.error(f"❌ Trimming failed: {result.stderr}")
            return input_path
            
    except Exception as e:
        logger.error(f"❌ Trim error: {e}")
        return input_path

# =============================================================================
# ✅ NEW FUNCTION: Convert English Audio to Hindi using FFmpeg
# =============================================================================
def convert_audio_to_hindi(english_audio_path):
    """
    Convert English audio to Hindi using speech-to-text and text-to-speech
    Note: This is a placeholder. You'll need to integrate with a translation API
    """
    try:
        # Generate Hindi filename
        hindi_filename = english_audio_path.replace('.mp3', '_hindi.mp3')
        if hindi_filename == english_audio_path:
            hindi_filename = english_audio_path.replace('.mp3', '') + '_hindi.mp3'
        
        # Check if FFmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except:
            logger.error("❌ FFmpeg not installed. Please install FFmpeg for audio conversion")
            # For now, just copy the file
            shutil.copy2(english_audio_path, hindi_filename)
            logger.info(f"⚠️ Using English audio as Hindi placeholder: {hindi_filename}")
            return hindi_filename
        
        # For now, we'll just copy the English audio as Hindi
        # In production, you would:
        # 1. Extract speech from English audio using speech-to-text (Google Speech API)
        # 2. Translate text to Hindi using Google Translate API
        # 3. Convert Hindi text to speech using text-to-speech (Google TTS)
        
        # Placeholder: Copy English as Hindi for now
        shutil.copy2(english_audio_path, hindi_filename)
        logger.info(f"⚠️ Using English audio as Hindi placeholder: {hindi_filename}")
        logger.info("🔧 To implement real conversion, integrate with Google Cloud Speech-to-Text + Translate + Text-to-Speech")
        
        return hindi_filename
        
    except Exception as e:
        logger.error(f"❌ Audio conversion error: {e}")
        return None

# =============================================================================
# ✅ FIXED: Fetch English Morning News (8:00-8:30 AM)
# =============================================================================
def fetch_english_morning_news():
    """
    Fetch English morning news from the specific URL
    URL: https://www.newsonair.gov.in/national-bulletins/?listen_news_cat=morning-news&listen_news_lang=english
    """
    session = get_session()
    
    # The exact URL provided
    target_url = "https://www.newsonair.gov.in/national-bulletins/?listen_news_cat=morning-news&listen_news_lang=english"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        logger.info(f"🔍 Fetching English morning news from: {target_url}")
        
        response = session.get(target_url, headers=headers, timeout=30, verify=True)
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP {response.status_code} for English morning news")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        audio_urls = []
        
        # Method 1: Find audio player with morning news
        # Look for audio elements specifically for morning news
        audio_players = soup.find_all("div", class_=re.compile(r"audio-player|player|media-player|bulletins"))
        
        for player in audio_players:
            # Find audio tags
            audio = player.find("audio")
            if audio:
                source = audio.find("source")
                if source and source.get("src"):
                    url = source["src"].strip()
                    if not url.startswith("http"):
                        url = "https://www.newsonair.gov.in" + url.lstrip("/")
                    if ".mp3" in url.lower():
                        audio_urls.append(url)
            
            # Find direct links
            for a in player.find_all("a", href=True):
                href = a["href"].strip()
                if ".mp3" in href.lower():
                    if not href.startswith("http"):
                        href = "https://www.newsonair.gov.in" + href.lstrip("/")
                    audio_urls.append(href)
        
        # Method 2: Find all MP3 links in the page
        if not audio_urls:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if ".mp3" in href.lower():
                    # Check if it's morning news
                    link_text = a.get_text().lower()
                    if "morning" in link_text or "प्रातः" in link_text:
                        if not href.startswith("http"):
                            href = "https://www.newsonair.gov.in" + href.lstrip("/")
                        audio_urls.append(href)
        
        # Method 3: Regex fallback
        if not audio_urls:
            mp3_pattern = r'https?://[^\s"\'<>]+\.mp3(?:\?[^\s"\'<>]*)?'
            matches = re.findall(mp3_pattern, response.text)
            for url in matches:
                clean_url = url.split('"')[0].split("'")[0].strip()
                if "morning" in clean_url.lower() or "प्रातः" in response.text.lower():
                    audio_urls.append(clean_url)
        
        # Remove duplicates
        seen = set()
        unique_urls = [u for u in audio_urls if not (u in seen or seen.add(u))]
        
        if unique_urls:
            # Get the latest/primary morning news URL
            latest_url = resolve_final_url(unique_urls[0], session)
            now = get_ist_time()
            date_display = now.strftime("%d-%m-%Y")
            
            bulletin = {
                "url": latest_url,
                "language": "english",
                "filename": latest_url.split("/")[-1].split("?")[0],
                "display_name": f"AIR_MORNING_NEWS_ENGLISH_{date_display}.mp3",
                "time": "Morning News (8:00-8:30 AM)",
                "date": date_display,
                "source_page": target_url,
                "duration": 0
            }
            logger.info(f"✅ English morning news found: {latest_url}")
            return [bulletin]
        
        logger.warning("⚠️ No English morning news found in the page")
        return []
        
    except Exception as e:
        logger.error(f"❌ Error fetching English morning news: {e}", exc_info=True)
        return []

# =============================================================================
# ✅ MAIN FUNCTION: Fetch both English and Hindi news
# =============================================================================
def fetch_audio_bulletins():
    """
    Fetch English morning news and convert to Hindi
    Returns: Dict with 'english' and 'hindi' bulletin data
    """
    try:
        # Get English morning news
        logger.info("📡 Fetching English morning news...")
        english_bulletins = fetch_english_morning_news()
        
        if not english_bulletins:
            logger.error("❌ Failed to fetch English morning news")
            return {"english": None, "hindi": None}
        
        logger.info(f"✅ Found {len(english_bulletins)} English bulletin(s)")
        english_bulletin = english_bulletins[0]
        
        # Download English audio temporarily to check duration
        temp_path = None
        try:
            temp_path = download_audio_temp(english_bulletin["url"])
            
            if temp_path:
                # Check duration
                duration_valid, duration = validate_audio_duration(temp_path)
                english_bulletin['duration'] = duration
                
                if not duration_valid and not Config.ALLOW_LONGER_AUDIO and not Config.AUTO_TRIM_AUDIO:
                    logger.error(f"❌ Audio duration {duration:.2f}s is outside {Config.MIN_AUDIO_DURATION_SECONDS}-{Config.MAX_AUDIO_DURATION_SECONDS}s range and auto-trim is disabled")
                    return {"english": None, "hindi": None}
        except Exception as e:
            logger.warning(f"⚠️ Could not validate duration: {e}")
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        # For Hindi, we'll convert the English audio
        hindi_bulletin = english_bulletin.copy()
        hindi_bulletin['language'] = 'hindi'
        hindi_bulletin['display_name'] = english_bulletin['display_name'].replace('ENGLISH', 'HINDI')
        hindi_bulletin['url'] = english_bulletin['url']  # Will be converted after download
        
        return {
            "english": english_bulletin,
            "hindi": hindi_bulletin
        }
    except Exception as e:
        logger.error(f"❌ Error in fetch_audio_bulletins: {e}", exc_info=True)
        return {"english": None, "hindi": None}

def download_audio_temp(url):
    """Download audio to temp file for checking"""
    session = get_session()
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            response = session.get(url, stream=True, timeout=60)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            return tmp.name
    except Exception as e:
        logger.error(f"❌ Temp download error: {e}")
        return None

# -----------------------------
# DOWNLOAD AUDIO WITH DURATION CHECK
# -----------------------------
def download_audio(bulletin, max_retries=3):
    """Download audio file with duration validation and optional trimming"""
    session = get_session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Referer": "https://www.newsonair.gov.in/",
    }
    
    for attempt in range(max_retries):
        try:
            url = bulletin["url"]
            filename = bulletin["display_name"]
            local_path = os.path.join(Config.AUDIO_DIR, filename)
            
            # If it's Hindi and we already have English, we need to convert
            if bulletin['language'] == 'hindi':
                english_path = local_path.replace('HINDI', 'ENGLISH')
                if os.path.exists(english_path):
                    logger.info(f"🔄 Converting English to Hindi: {filename}")
                    hindi_path = convert_audio_to_hindi(english_path)
                    if hindi_path and os.path.exists(hindi_path):
                        return hindi_path
            
            logger.info(f"⬇️ Downloading: {filename} (attempt {attempt+1}/{max_retries})")
            
            response = session.get(url, headers=headers, stream=True, timeout=120, verify=True, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "application/json" in content_type:
                logger.error(f"❌ Got {content_type} instead of audio!")
                return None
            
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if not os.path.exists(local_path):
                logger.error(f"❌ File not saved: {local_path}")
                return None
            
            file_size = os.path.getsize(local_path)
            logger.info(f"📦 Downloaded {file_size/1024:.1f} KB to {filename}")
            
            # Validate MP3 header
            with open(local_path, "rb") as f:
                header = f.read(10)
                is_valid_mp3 = (
                    (header[0] == 0xFF and (header[1] & 0xE0) == 0xE0) or
                    header[:3] == b'ID3' or
                    header[:4] == b'\x00\x00\x00\x1c'
                )
                if not is_valid_mp3 and file_size < 50000:
                    logger.error(f"❌ Invalid audio file: {file_size} bytes")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    return None
            
            # Check duration
            duration_valid, duration = validate_audio_duration(local_path)
            bulletin['duration'] = duration
            
            # If audio is too long and auto-trim is enabled, trim it
            if duration and duration > Config.MAX_AUDIO_DURATION_SECONDS and Config.AUTO_TRIM_AUDIO:
                logger.info(f"✂️ Audio is {duration:.2f}s, trimming to {Config.MAX_AUDIO_DURATION_SECONDS}s")
                trimmed_path = trim_audio_to_duration(local_path, Config.MAX_AUDIO_DURATION_SECONDS)
                
                # Replace original with trimmed if trimming succeeded
                if trimmed_path != local_path and os.path.exists(trimmed_path):
                    # Remove original
                    os.remove(local_path)
                    # Rename trimmed to original name
                    os.rename(trimmed_path, local_path)
                    logger.info(f"✅ Trimmed audio saved as: {local_path}")
                    
                    # Update duration
                    new_duration = get_audio_duration(local_path)
                    bulletin['duration'] = new_duration
            
            return local_path
                
        except ssl.SSLError as e:
            logger.error(f"❌ SSL error downloading: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"⚠️ Connection error: {e}")
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ Download timeout")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "Unknown"
            logger.error(f"❌ HTTP {status} error: {e}")
        except Exception as e:
            logger.error(f"❌ Download error: {e}", exc_info=True)
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    
    return None