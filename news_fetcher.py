import requests
from bs4 import BeautifulSoup
import os
import logging
import re
import time
import ssl
from datetime import datetime
import pytz
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import mutagen
from mutagen.mp3 import MP3

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
        return False, duration

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

# =============================================================================
# ✅ HELPER: Language Matching
# =============================================================================
def _matches_language(url, text_content, language):
    """Check if URL or page content matches requested language"""
    url_lower = url.lower()
    text_lower = text_content.lower() if text_content else ""
    
    if language == "english":
        # English: should NOT contain hindi indicators
        hindi_indicators = ['hindi', '_hi', '-hi', '/hi/', 'hi_', '_hindi', '%E0%A4', 'hindi-bulletins']
        return not any(ind in url_lower or ind in text_lower for ind in hindi_indicators)
    elif language == "hindi":
        # Hindi: should contain hindi indicators
        hindi_indicators = ['hindi', '_hi', '-hi', '/hi/', 'hi_', '_hindi', '%E0%A4', 'hindi-bulletins', 'हिंदी']
        return any(ind in url_lower or ind in text_lower for ind in hindi_indicators)
    return True

# =============================================================================
# ✅ FIXED: FETCH BULLETIN WITH PROPER .GOV.IN URLS
# =============================================================================
def fetch_audio_bulletins(language="english", max_retries=3):
    """
    Fetch audio bulletin URLs from AIR website (.gov.in only)
    Returns: List of bulletin dicts or empty list if failed
    """
    session = get_session()
    
    # ✅ ONLY use official .gov.in domain (no .com to avoid SSL issues)
    base_url = "https://www.newsonair.gov.in"
    
    # Try these URL patterns in order
    url_patterns = {
        "english": [
            f"{base_url}/national-bulletins/",
            f"{base_url}/",
        ],
        "hindi": [
            f"{base_url}/main/hindi-bulletins/",  # Old pattern
            f"{base_url}/national-bulletins/",     # Hindi may be on same page
            f"{base_url}/",                         # Fallback to homepage
        ]
    }
    
    urls_to_try = url_patterns.get(language, [f"{base_url}/national-bulletins/"])
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9" if language == "english" else "hi-IN,hi;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    for source_url in urls_to_try:
        for attempt in range(max_retries):
            try:
                logger.info(f"🔍 Fetching {language.upper()} from: {source_url} (attempt {attempt+1})")
                
                if attempt > 0:
                    time.sleep(2 ** attempt)
                
                # ✅ Use verify=True for security, but catch SSL errors gracefully
                response = session.get(source_url, headers=headers, timeout=30, verify=True)
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ HTTP {response.status_code} for {language} at {source_url}")
                    continue
                
                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type:
                    continue
                
                soup = BeautifulSoup(response.text, "html.parser")
                audio_urls = []
                
                # Method 1: Find <audio> tags
                for audio in soup.find_all("audio"):
                    source = audio.find("source")
                    if source and source.get("src"):
                        link = source["src"].strip()
                        if not link.startswith("http"):
                            link = base_url + link.lstrip("/")
                        if ".mp3" in link.lower() and _matches_language(link, soup.get_text(), language):
                            audio_urls.append(link)
                
                # Method 2: Find <a> links to MP3
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if ".mp3" in href.lower():
                        if not href.startswith("http"):
                            href = base_url + href.lstrip("/")
                        if _matches_language(href, a.get_text(), language):
                            audio_urls.append(href)
                
                # Method 3: Regex fallback
                if not audio_urls:
                    mp3_pattern = r'https?://[^\s"\'<>]+\.mp3(?:\?[^\s"\'<>]*)?'
                    matches = re.findall(mp3_pattern, response.text)
                    for m in matches:
                        clean_url = m.split('"')[0].split("'")[0].strip()
                        if _matches_language(clean_url, response.text, language) and clean_url not in audio_urls:
                            audio_urls.append(clean_url)
                
                # Remove duplicates
                seen = set()
                unique_urls = [u for u in audio_urls if not (u in seen or seen.add(u))]
                audio_urls = unique_urls
                
                if audio_urls:
                    latest = resolve_final_url(audio_urls[0], session)
                    now = get_ist_time()
                    date_display = now.strftime("%d-%m-%Y")
                    
                    bulletin = {
                        "url": latest,
                        "language": language,
                        "filename": latest.split("/")[-1].split("?")[0],
                        "display_name": f"AIR_NEWS_{language.upper()}_{date_display}.mp3",
                        "time": "Latest",
                        "date": date_display,
                        "source_page": source_url
                    }
                    logger.info(f"✅ {language.upper()} bulletin found: {latest}")
                    return [bulletin]
                
                logger.warning(f"⚠️ No {language} bulletins found at {source_url}")
                
            except ssl.SSLError as e:
                logger.warning(f"⚠️ SSL error for {source_url}: {e}")
                # Don't retry SSL errors - try next URL instead
                break
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"⚠️ Connection error: {e}")
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Timeout fetching {language}")
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}", exc_info=True)
    
    logger.error(f"❌ Failed to fetch {language} from all URLs")
    return []

# -----------------------------
# DOWNLOAD AUDIO WITH DURATION CHECK
# -----------------------------
def download_audio(bulletin, max_retries=3):
    """Download audio file with duration validation (4-5 minutes)"""
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
            
            logger.info(f"⬇️ Downloading: {filename} (attempt {attempt+1}/{max_retries})")
            
            response = session.get(url, headers=headers, stream=True, timeout=120, verify=True, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "application/json" in content_type:
                logger.error(f"❌ Got {content_type} instead of audio!")
                return None
            
            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
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