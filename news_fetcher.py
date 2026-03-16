import requests
from bs4 import BeautifulSoup
import os
import logging
import re
import time
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
# ✅ CONFIGURATION: FFmpeg Path
# =============================================================================
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

def get_ffmpeg_path():
    """Return FFmpeg executable path"""
    if os.path.isfile(FFMPEG_PATH):
        return FFMPEG_PATH
    if os.name == 'nt' and not FFMPEG_PATH.lower().endswith('.exe'):
        exe_path = FFMPEG_PATH + '.exe'
        if os.path.isfile(exe_path):
            return exe_path
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return ffmpeg_in_path
    logger.error(f"❌ FFmpeg NOT found")
    return FFMPEG_PATH

# -----------------------------
# SESSION WITH RETRY
# -----------------------------
def create_session():
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
    global _session
    if _session is None:
        _session = create_session()
    return _session

def get_ist_time():
    return datetime.now(pytz.timezone(Config.TIMEZONE))

# -----------------------------
# RESOLVE FINAL URL
# -----------------------------
def resolve_final_url(url, session=None):
    if session is None:
        session = get_session()
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = session.head(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code in [200, 301, 302]:
            return resp.url
        resp = session.get(url, headers=headers, timeout=15, stream=True)
        return resp.url
    except:
        return url

# -----------------------------
# AUDIO DURATION
# -----------------------------
def get_audio_duration(file_path):
    try:
        audio = MP3(file_path)
        return audio.info.length
    except:
        return None

def validate_audio_duration(file_path):
    """Validate audio is within 1-5 minutes (60-300 seconds)"""
    duration = get_audio_duration(file_path)
    if duration is None:
        logger.warning("⚠️ Could not detect duration, accepting file")
        return True, None
    
    min_dur = Config.MIN_AUDIO_DURATION_SECONDS
    max_dur = Config.MAX_AUDIO_DURATION_SECONDS
    
    if duration < min_dur:
        logger.warning(f"⚠️ Audio too short: {duration:.2f}s < {min_dur}s")
        return False, duration
    if duration > max_dur:
        logger.warning(f"⚠️ Audio too long: {duration:.2f}s > {max_dur}s")
        return False, duration
    
    logger.info(f"✅ Duration valid: {duration:.2f}s")
    return True, duration

# =============================================================================
# ✅ FIXED: Check for 7:00-7:30 AM time slot (ACCEPTS 07:00 to 07:30)
# =============================================================================
def is_7am_time_slot(text):
    """
    Check if text contains news from 7:00-7:30 AM slot
    Accepts: 07:00, 07:05, 07:10, 07:15, 07:20, 07:25, 07:30
    Rejects: 06:xx, 08:xx, 09:xx, etc.
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # ✅ ACCEPT: Any time from 07:00 to 07:30
    # This pattern matches 07:00, 07:05, 07:10, 07:15, 07:20, 07:25, 07:30
    seven_am_pattern = r'(0?7\s*:\s*[0-3][0-9])'
    has_7am = bool(re.search(seven_am_pattern, text_lower))
    
    # Also check for Hindi "सात" (seven)
    if not has_7am:
        has_7am = bool(re.search(r'सात\s*(बजे|प्रातः|सुबह)', text_lower))
    
    if not has_7am:
        return False
    
    # ❌ REJECT: Times outside 7:00-7:30 range
    # Check for 8 AM, 9 AM, 6 AM, etc.
    reject_patterns = [
        r'0?8\s*:\s*\d+', r'0?9\s*:\s*\d+', r'1[0-2]\s*:\s*\d+',
        r'0?6\s*:\s*\d+', r'0?[0-5]\s*:\s*\d+',
        r'eight', r'nine', r'ten', r'eleven', r'twelve',
        r'आठ', r'नौ', r'दस'
    ]
    
    for pattern in reject_patterns:
        if re.search(pattern, text_lower):
            logger.debug(f"⚠️ Rejected (other time): {text[:100]}")
            return False
    
    logger.info(f"✅ Accepted 7AM slot: {text[:80]}")
    return True

# =============================================================================
# ✅ FIXED: Fetch English 7:00-7:30 AM News (From Screenshot)
# =============================================================================
def fetch_english_morning_news():
    """Fetch English news from 7:00-7:30 AM slot (e.g., 07:05)"""
    session = get_session()
    target_url = "https://www.newsonair.gov.in/national-bulletins/?listen_news_cat=&listen_news_lang=english&listen_news_date=&listen_news_time=&submit=Search"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    
    try:
        logger.info(f"🔍 Fetching English 7AM news...")
        response = session.get(target_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        audio_urls = []
        
        # Look for news cards/containers
        for div in soup.find_all("div", class_=re.compile(r"col|card|bulletin|news-item")):
            # Find audio or links
            audio = div.find("audio")
            links = div.find_all("a", href=True)
            
            # Check audio tags
            if audio:
                source = audio.find("source")
                if source and source.get("src"):
                    url = source["src"].strip()
                    if ".mp3" in url.lower():
                        context = div.get_text()
                        if is_7am_time_slot(context):
                            if not url.startswith("http"):
                                url = "https://www.newsonair.gov.in" + url.lstrip("/")
                            audio_urls.append((url, context))
                            logger.info(f"✅ Found English audio in <audio>: {url}")
            
            # Check link tags
            for a in links:
                href = a["href"].strip()
                if ".mp3" in href.lower():
                    link_text = a.get_text() + " " + a.get("title", "")
                    context = div.get_text() + " " + link_text
                    
                    if is_7am_time_slot(context):
                        if not href.startswith("http"):
                            href = "https://www.newsonair.gov.in" + href.lstrip("/")
                        audio_urls.append((href, context))
                        logger.info(f"✅ Found English audio in <a>: {href}")
        
        # Remove duplicates
        seen = set()
        unique_urls = []
        for url, ctx in audio_urls:
            if url and url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        logger.info(f"🔎 Found {len(unique_urls)} English 7AM URLs")
        
        if unique_urls:
            latest_url = resolve_final_url(unique_urls[0], session)
            now = get_ist_time()
            date_display = now.strftime("%d-%m-%Y")
            
            bulletin = {
                "url": latest_url,
                "language": "english",
                "filename": latest_url.split("/")[-1].split("?")[0] or f"air_7am_en_{date_display}.mp3",
                "display_name": f"AIR_7AM_NEWS_ENGLISH_{date_display}.mp3",
                "time": "Morning News (7:00-7:30 AM)",
                "date": date_display,
                "source_page": target_url,
                "duration": 0
            }
            logger.info(f"✅ English 7AM bulletin: {latest_url}")
            return [bulletin]
        
        logger.warning("⚠️ No English 7:00-7:30 AM news found")
        # Debug: log what we found
        for div in soup.find_all("div", class_=re.compile(r"col|card"))[:5]:
            logger.debug(f"📄 Found: {div.get_text()[:200]}")
        return []
        
    except Exception as e:
        logger.error(f"❌ Error fetching English 7AM news: {e}", exc_info=True)
        return []

# =============================================================================
# ✅ FIXED: Fetch Hindi 7:00-7:30 AM News (From Screenshot)
# =============================================================================
def fetch_hindi_morning_news():
    """Fetch Hindi news from 7:00-7:30 AM slot (e.g., 07:00)"""
    session = get_session()
    target_url = "https://www.newsonair.gov.in/national-bulletins/?listen_news_cat=&listen_news_lang=hindi&listen_news_date=&listen_news_time=&submit=Search"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
    
    try:
        logger.info(f"🔍 Fetching Hindi 7AM news...")
        response = session.get(target_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        audio_urls = []
        
        # Look for news cards
        for div in soup.find_all("div", class_=re.compile(r"col|card|bulletin|news-item")):
            audio = div.find("audio")
            links = div.find_all("a", href=True)
            
            # Check audio tags
            if audio:
                source = audio.find("source")
                if source and source.get("src"):
                    url = source["src"].strip()
                    if ".mp3" in url.lower():
                        context = div.get_text()
                        if is_7am_time_slot(context):
                            if not url.startswith("http"):
                                url = "https://www.newsonair.gov.in" + url.lstrip("/")
                            audio_urls.append((url, context))
                            logger.info(f"✅ Found Hindi audio in <audio>: {url}")
            
            # Check link tags
            for a in links:
                href = a["href"].strip()
                if ".mp3" in href.lower():
                    link_text = a.get_text() + " " + a.get("title", "")
                    context = div.get_text() + " " + link_text
                    
                    if is_7am_time_slot(context):
                        if not href.startswith("http"):
                            href = "https://www.newsonair.gov.in" + href.lstrip("/")
                        audio_urls.append((href, context))
                        logger.info(f"✅ Found Hindi audio in <a>: {href}")
        
        # Remove duplicates
        seen = set()
        unique_urls = [u for u, _ in audio_urls if u and u not in seen and not seen.add(u)]
        
        logger.info(f"🔎 Found {len(unique_urls)} Hindi 7AM URLs")
        
        if unique_urls:
            latest_url = resolve_final_url(unique_urls[0], session)
            now = get_ist_time()
            date_display = now.strftime("%d-%m-%Y")
            
            bulletin = {
                "url": latest_url,
                "language": "hindi",
                "filename": latest_url.split("/")[-1].split("?")[0] or f"air_7am_hi_{date_display}.mp3",
                "display_name": f"AIR_7AM_NEWS_HINDI_{date_display}.mp3",
                "time": "Morning News (7:00-7:30 AM)",
                "date": date_display,
                "source_page": target_url,
                "duration": 0
            }
            logger.info(f"✅ Hindi 7AM bulletin: {latest_url}")
            return [bulletin]
        
        logger.warning("⚠️ No Hindi 7:00-7:30 AM news found")
        return []
        
    except Exception as e:
        logger.error(f"❌ Error fetching Hindi 7AM news: {e}", exc_info=True)
        return []

# =============================================================================
# ✅ MAIN: Fetch Both Languages
# =============================================================================
def fetch_audio_bulletins():
    """Fetch English AND Hindi 7:00-7:30 AM news"""
    result = {"english": None, "hindi": None}
    
    try:
        eng_list = fetch_english_morning_news()
        if eng_list:
            result["english"] = eng_list[0]
            logger.info(f"✅ English 7AM ready")
        
        hi_list = fetch_hindi_morning_news()
        if hi_list:
            result["hindi"] = hi_list[0]
            logger.info(f"✅ Hindi 7AM ready")
        
        if not result["english"] and not result["hindi"]:
            logger.warning("⚠️ No 7:00-7:30 AM news found")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ fetch_audio_bulletins error: {e}", exc_info=True)
        return result

# =============================================================================
# ✅ DOWNLOAD AUDIO
# =============================================================================
def download_audio_temp(url):
    """Download to temp file"""
    session = get_session()
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            resp = session.get(url, stream=True, timeout=60)
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            return tmp.name
    except Exception as e:
        logger.error(f"❌ Temp download error: {e}")
        return None

def download_audio(bulletin, max_retries=3):
    """Download audio - NO trimming"""
    session = get_session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Referer": "https://www.newsonair.gov.in/",
    }
    
    for attempt in range(max_retries):
        try:
            url = bulletin["url"]
            filename = bulletin["display_name"]
            local_path = os.path.join(Config.AUDIO_DIR, filename)
            
            logger.info(f"⬇️ Downloading: {filename}")
            
            response = session.get(url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if not os.path.exists(local_path):
                logger.error("❌ File not saved")
                return None
            
            duration = get_audio_duration(local_path)
            bulletin['duration'] = duration or 0
            
            valid, dur = validate_audio_duration(local_path)
            if not valid:
                logger.error(f"❌ Invalid duration {dur:.2f}s")
                if os.path.exists(local_path):
                    os.remove(local_path)
                return None
            
            logger.info(f"🎵 Duration: {bulletin['duration']:.2f}s ✅")
            return local_path
            
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            continue
    return None

# =============================================================================
# ✅ TEST
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("🚀 Testing AIR 7AM News Fetcher")
    
    result = fetch_audio_bulletins()
    
    if result.get("english"):
        path = download_audio(result["english"])
        if path:
            
            logger.info(f"💾 English saved: {path}")
    
    if result.get("hindi"):
        path = download_audio(result["hindi"])
        if path:
            logger.info(f"💾 Hindi saved: {path}")
    
    logger.info("✨ Test complete")