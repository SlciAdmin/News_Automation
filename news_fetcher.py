import requests
from bs4 import BeautifulSoup
import os
import logging
import re
import time
from datetime import datetime
import pytz
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

def create_session():
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
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

def get_audio_duration(file_path):
    try:
        audio = MP3(file_path)
        return audio.info.length
    except Exception as e:
        logger.warning(f"⚠️ Could not get duration: {e}")
        return None

def validate_audio_duration(file_path):
    duration = get_audio_duration(file_path)
    if duration is None: return True, duration
    min_dur = Config.MIN_AUDIO_DURATION_SECONDS
    max_dur = Config.MAX_AUDIO_DURATION_SECONDS
    if min_dur <= duration <= max_dur:
        return True, duration
    return False, duration

def _matches_language(url, text_content, language):
    url_lower = url.lower()
    text_lower = text_content.lower() if text_content else ""
    
    if language == "english":
        hindi_indicators = ['hindi', '_hi', '-hi', '/hi/', 'hi_', '_hindi', '%E0%A4', 'hindi-bulletins', 'हिंदी']
        return not any(ind in url_lower or ind in text_lower for ind in hindi_indicators)
    elif language == "hindi":
        hindi_indicators = ['hindi', '_hi', '-hi', '/hi/', 'hi_', '_hindi', '%E0%A4', 'hindi-bulletins', 'हिंदी']
        return any(ind in url_lower or ind in text_lower for ind in hindi_indicators)
    return True

def fetch_audio_bulletins(language="english", max_retries=3):
    session = get_session()
    
    # ✅ Use Official Links Provided
    if language == "hindi":
        base_url = Config.NEWS_SOURCE_URL_HINDI
    else:
        base_url = Config.NEWS_SOURCE_URL_ENGLISH
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9" if language == "english" else "hi-IN,hi;q=0.9",
    }
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔍 Fetching {language.upper()} from: {base_url} (attempt {attempt+1})")
            if attempt > 0: time.sleep(2 ** attempt)
            
            response = session.get(base_url, headers=headers, timeout=30, verify=True)
            if response.status_code != 200:
                logger.warning(f"⚠️ HTTP {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.text, "html.parser")
            audio_urls = []
            
            # Method 1: Find <audio> tags
            for audio in soup.find_all("audio"):
                source = audio.find("source")
                if source and source.get("src"):
                    link = source["src"].strip()
                    if not link.startswith("http"): link = "https://www.newsonair.gov.in" + link.lstrip("/")
                    if ".mp3" in link.lower() and _matches_language(link, soup.get_text(), language):
                        audio_urls.append(link)
            
            # Method 2: Find <a> links to MP3
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if ".mp3" in href.lower():
                    if not href.startswith("http"): href = "https://www.newsonair.gov.in" + href.lstrip("/")
                    if _matches_language(href, a.get_text(), language):
                        audio_urls.append(href)
            
            if audio_urls:
                latest = audio_urls[0]
                now = datetime.now(pytz.timezone(Config.TIMEZONE))
                date_display = now.strftime("%d-%m-%Y")
                bulletin = {
                    "url": latest,
                    "language": language,
                    "filename": latest.split("/")[-1].split("?")[0],
                    "display_name": f"AIR_NEWS_{language.upper()}_{date_display}.mp3",
                    "date": date_display,
                    "source_page": base_url
                }
                logger.info(f"✅ {language.upper()} bulletin found: {latest}")
                return [bulletin]
                
            logger.warning(f"⚠️ No {language} bulletins found")
        except Exception as e:
            logger.error(f"❌ Error fetching {language}: {e}")
            
    return []

def download_audio(bulletin, max_retries=3):
    session = get_session()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for attempt in range(max_retries):
        try:
            url = bulletin["url"]
            filename = bulletin["display_name"]
            local_path = os.path.join(Config.AUDIO_DIR, filename)
            
            logger.info(f"⬇️ Downloading: {filename} (attempt {attempt+1})")
            response = session.get(url, headers=headers, stream=True, timeout=120, verify=True)
            response.raise_for_status()
            
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            
            if not os.path.exists(local_path):
                logger.error(f"❌ File not saved")
                return None
                
            duration_valid, duration = validate_audio_duration(local_path)
            bulletin['duration'] = duration
            return local_path
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            if attempt < max_retries - 1: time.sleep(2 ** attempt)
    return None