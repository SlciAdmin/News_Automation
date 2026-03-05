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

# =============================================================================
# ✅ CONFIGURATION: FFmpeg Path (Windows Example)
# =============================================================================
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"   # Update this path to your FFmpeg installation

# For cross-platform compatibility, fallback to system PATH if custom path doesn't exist
def get_ffmpeg_path():
    """Return FFmpeg executable path - robust version"""
    logger.debug(f"🔍 Checking FFMPEG_PATH: {FFMPEG_PATH}")
    
    # Try explicit path
    if os.path.isfile(FFMPEG_PATH):
        logger.info(f"✅ FFmpeg found at: {FFMPEG_PATH}")
        return FFMPEG_PATH
    
    # Try with .exe extension
    if os.name == 'nt' and not FFMPEG_PATH.lower().endswith('.exe'):
        exe_path = FFMPEG_PATH + '.exe'
        if os.path.isfile(exe_path):
            logger.info(f"✅ FFmpeg found at: {exe_path}")
            return exe_path
    
    # Fallback to system PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        logger.info(f"✅ FFmpeg found in PATH: {ffmpeg_in_path}")
        return ffmpeg_in_path
    
    logger.error(f"❌ FFmpeg NOT found at: {FFMPEG_PATH}")
    return FFMPEG_PATH

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
# HELPER: Resolve Final URL
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
    """Validate audio duration and return validity status + duration value"""
    
    duration = get_audio_duration(file_path)

    if duration is None:
        logger.warning("⚠️ Could not detect audio duration. Accepting file.")
        return True, None

    min_dur = Config.MIN_AUDIO_DURATION_SECONDS
    max_dur = Config.MAX_AUDIO_DURATION_SECONDS

    # Don't reject long audio - let trim handle it
    if duration > max_dur:
        logger.info(f"📏 Audio is {duration:.2f}s (will trim to {max_dur}s)")
        return True, duration

    # Too short
    if duration < min_dur:
        logger.warning(f"⚠️ Audio too short: {duration:.2f}s (min required: {min_dur}s)")
        return False, duration

    # Perfect range
    logger.info(f"✅ Duration valid: {duration:.2f}s")
    return True, duration


# =============================================================================
# ✅ MERGED: Trim Audio to Duration using FFmpeg (with FFMPEG_PATH)
# =============================================================================
def trim_audio_to_duration(input_path, max_duration=300):
    """
    Trim audio using FFmpeg safely and reliably
    """

    try:
        ffmpeg = get_ffmpeg_path()

        # check ffmpeg
        try:
            subprocess.run([ffmpeg, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception:
            logger.error("❌ FFmpeg not working or not found")
            return input_path

        # output path
        output_path = input_path.replace(".mp3", "_trimmed.mp3")

        cmd = [
            ffmpeg,
            "-y",
            "-i", input_path,
            "-ss", "0",
            "-t", str(max_duration),
            "-acodec", "copy",
            output_path
        ]

        logger.info(f"✂️ Trimming audio to {max_duration} seconds")

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"✅ Trim successful: {output_path}")
            return output_path

        logger.error("❌ FFmpeg trimming failed")
        return input_path

    except Exception as e:
        logger.error(f"❌ Trim error: {e}")
        return input_path

# =============================================================================
# ✅ Convert English Audio to Hindi using FFmpeg (Placeholder)
# =============================================================================
def convert_audio_to_hindi(english_audio_path):
    """
    Convert English audio to Hindi using speech-to-text and text-to-speech
    Note: This is a placeholder. You'll need to integrate with a translation API
    """
    try:
        ffmpeg_exe = get_ffmpeg_path()
        
        # Generate Hindi filename
        hindi_filename = english_audio_path.replace('.mp3', '_hindi.mp3')
        if hindi_filename == english_audio_path:
            hindi_filename = english_audio_path.replace('.mp3', '') + '_hindi.mp3'
        
        # Check if FFmpeg is available (for future real conversion)
        try:
            subprocess.run([ffmpeg_exe, '-version'], capture_output=True, check=True)
        except:
            logger.warning(f"⚠️ FFmpeg not available at {ffmpeg_exe}, using fallback copy method")
        
        # For now, we'll just copy the English audio as Hindi placeholder
        shutil.copy2(english_audio_path, hindi_filename)
        logger.info(f"⚠️ Using English audio as Hindi placeholder: {hindi_filename}")
        logger.info("🔧 To implement real conversion, integrate with Google Cloud Speech-to-Text + Translate + Text-to-Speech")
        
        return hindi_filename
        
    except Exception as e:
        logger.error(f"❌ Audio conversion error: {e}")
        return None

# =============================================================================
# ✅ Fetch English Morning News (8:00-8:30 AM)
# =============================================================================
def fetch_english_morning_news():
    """
    Fetch English morning news from the specific URL
    URL: https://www.newsonair.gov.in/national-bulletins/?listen_news_cat=morning-news&listen_news_lang=english
    """
    session = get_session()
    
    # The exact URL provided (stripped trailing spaces)
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
        audio_players = soup.find_all("div", class_=re.compile(r"audio-player|player|media-player|bulletins"))
        
        for player in audio_players:
            audio = player.find("audio")
            if audio:
                source = audio.find("source")
                if source and source.get("src"):
                    url = source["src"].strip()
                    if not url.startswith("http"):
                        url = "https://www.newsonair.gov.in" + url.lstrip("/")
                    if ".mp3" in url.lower():
                        audio_urls.append(url)
            
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
                duration_valid, duration = validate_audio_duration(temp_path)
                english_bulletin['duration'] = duration
                
                if not duration_valid and not Config.ALLOW_LONGER_AUDIO and not Config.AUTO_TRIM_AUDIO:
                    logger.error(f"❌ Audio duration {duration:.2f}s is outside {Config.MIN_AUDIO_DURATION_SECONDS}-{Config.MAX_AUDIO_DURATION_SECONDS}s range")
                    return {"english": None, "hindi": None}
        except Exception as e:
            logger.warning(f"⚠️ Could not validate duration: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        # For Hindi, we'll convert the English audio
        hindi_bulletin = english_bulletin.copy()
        hindi_bulletin['language'] = 'hindi'
        hindi_bulletin['display_name'] = english_bulletin['display_name'].replace('ENGLISH', 'HINDI')
        hindi_bulletin['url'] = english_bulletin['url']
        
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
# DOWNLOAD AUDIO WITH DURATION CHECK & FORCE TRIM
# -----------------------------
def download_audio(bulletin, max_retries=3):
    """Download audio file with duration validation and FORCE TRIM if too long"""
    session = get_session()

    headers = {
        "User-Agent": "Mozilla/5.0",
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

            # Hindi conversion
            if bulletin['language'] == 'hindi':
                english_path = local_path.replace('HINDI', 'ENGLISH')
                if os.path.exists(english_path):
                    logger.info(f"🔄 Converting English to Hindi: {filename}")
                    hindi_path = convert_audio_to_hindi(english_path)
                    if hindi_path and os.path.exists(hindi_path):
                        return hindi_path

            logger.info(f"⬇️ Downloading: {filename} (attempt {attempt+1}/{max_retries})")

            response = session.get(url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            if not os.path.exists(local_path):
                logger.error("❌ File not saved")
                return None

            file_size = os.path.getsize(local_path)
            logger.info(f"📦 Downloaded {file_size/1024:.1f} KB")

            # Validate MP3 header
            with open(local_path, "rb") as f:
                header = f.read(10)
                is_valid_mp3 = (
                    (header[0] == 0xFF and (header[1] & 0xE0) == 0xE0)
                    or header[:3] == b'ID3'
                )

                if not is_valid_mp3 and file_size < 50000:
                    logger.error("❌ Invalid audio file")
                    os.remove(local_path)
                    return None

            # Get duration but don't reject yet - use updated validate function
            duration_valid, duration = validate_audio_duration(local_path)
            bulletin['duration'] = duration

            # ===============================
            # ✅ TRIM IF TOO LONG
            # ===============================
            if duration and duration > Config.MAX_AUDIO_DURATION_SECONDS:
                logger.info(f"✂️ Audio too long ({duration:.2f}s). Trimming to {Config.MAX_AUDIO_DURATION_SECONDS}s...")
                
                trimmed_path = trim_audio_to_duration(
                    local_path,
                    Config.MAX_AUDIO_DURATION_SECONDS
                )
                
                if trimmed_path and os.path.exists(trimmed_path) and trimmed_path != local_path:
                    os.remove(local_path)
                    os.rename(trimmed_path, local_path)
                    logger.info(f"✅ Trim complete")
                    
                    # Get new duration after trim
                    new_duration = get_audio_duration(local_path)
                    bulletin['duration'] = new_duration
                    duration = new_duration  # Update duration variable for next check

            # Now check if final audio is too short
            if duration and duration < Config.MIN_AUDIO_DURATION_SECONDS:
                logger.error("❌ Audio too short after trim")
                os.remove(local_path)
                return None

            return local_path

        except Exception as e:
            logger.error(f"❌ Download error: {e}", exc_info=True)

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return None

# =============================================================================
# ✅ MAIN ENTRY POINT (Example Usage)
# =============================================================================
if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info("🚀 Starting AIR News Audio Fetcher")
    
    # Fetch bulletins
    result = fetch_audio_bulletins()
    
    if result.get("english"):
        logger.info(f"✅ English bulletin ready: {result['english']['display_name']}")
    
    if result.get("hindi"):
        logger.info(f"✅ Hindi bulletin ready: {result['hindi']['display_name']}")
    
    # Download the files
    if result.get("english"):
        eng_path = download_audio(result["english"])
        if eng_path:
            logger.info(f"💾 English audio saved: {eng_path}")
    
    if result.get("hindi"):
        hindi_path = download_audio(result["hindi"])
        if hindi_path:
            logger.info(f"💾 Hindi audio saved: {hindi_path}")
    
    logger.info("✨ Finished")