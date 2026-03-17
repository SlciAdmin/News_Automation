import requests
import os
import logging
import re
import time
from datetime import datetime
import pytz
from config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from bs4 import BeautifulSoup
import urllib.parse

logger = logging.getLogger(__name__)

# =============================================================================
# ✅ CONFIGURATION
# =============================================================================
BASE_URL = "https://www.newsonair.gov.in"
NATIONAL_BULLETINS_URL = f"{BASE_URL}/national-bulletins/"
AUDIO_ARCHIVE_URL = f"{BASE_URL}/audio-archive-search/"

# =============================================================================
# SESSION WITH RETRY - Simplified
# =============================================================================
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Set realistic browser headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    
    return session

_session = None
def get_session():
    global _session
    if _session is None:
        _session = create_session()
    return _session

def get_ist_time():
    return datetime.now(pytz.timezone(Config.TIMEZONE))

# =============================================================================
# ✅ METHOD 1: Direct page scraping (Most Reliable)
# =============================================================================
def fetch_from_national_bulletins(language):
    """
    Fetch audio bulletins directly from the national-bulletins page
    This is more reliable than the API
    """
    session = get_session()
    
    # Map language to URL parameter
    lang_param = "english" if language == "english" else "hindi"
    
    # Try different category combinations
    categories = ["", "morning-news", "samachar-prabhat", "evening-news", "news-at-nine"]
    
    all_bulletins = []
    
    for category in categories:
        if category:
            search_url = f"{NATIONAL_BULLETINS_URL}?listen_news_cat={category}&listen_news_lang={lang_param}"
        else:
            search_url = f"{NATIONAL_BULLETINS_URL}?listen_news_lang={lang_param}"
        
        try:
            logger.info(f"🔍 Scraping: {search_url}")
            response = session.get(search_url, timeout=20)
            
            if response.status_code != 200:
                logger.warning(f"⚠️ HTTP {response.status_code} for {search_url}")
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for bulletin items - common patterns
            bulletin_containers = []
            
            # Try different selectors
            selectors = [
                'div.col-md-12',
                'div.col-sm-12',
                'div.panel-body',
                'div.news-item',
                'div.latest-news-item',
                'div.bulletin-item',
                'li.media',
                'div.media',
                'div.post-item',
                'article.post'
            ]
            
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    bulletin_containers.extend(containers)
            
            # Also look for any div that might contain audio links
            if not bulletin_containers:
                bulletin_containers = soup.find_all('div', class_=re.compile(r'col|media|post|news|bulletin|item|list'))
            
            for container in bulletin_containers:
                # Look for audio tags
                audio_tag = container.find('audio')
                if audio_tag:
                    source = audio_tag.find('source')
                    if source and source.get('src'):
                        audio_url = source['src']
                        title_tag = container.find(['h2', 'h3', 'h4', 'h5', 'strong', 'p'])
                        title = title_tag.get_text(strip=True) if title_tag else "Morning News Bulletin"
                        
                        if 'mp3' in audio_url.lower():
                            bulletins = process_audio_url(audio_url, title, language, container.get_text())
                            all_bulletins.extend(bulletins)
                
                # Look for direct MP3 links
                for link in container.find_all('a', href=True):
                    href = link['href']
                    if '.mp3' in href.lower():
                        title = link.get_text(strip=True) or "Audio Bulletin"
                        bulletins = process_audio_url(href, title, language, container.get_text())
                        all_bulletins.extend(bulletins)
            
            # Also search the entire page for MP3 links
            if not all_bulletins:
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '.mp3' in href.lower():
                        title = link.get_text(strip=True) or "Audio Bulletin"
                        bulletins = process_audio_url(href, title, language, "")
                        all_bulletins.extend(bulletins)
                        
        except Exception as e:
            logger.debug(f"Error scraping {search_url}: {e}")
            continue
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_bulletins = []
    for bulletin in all_bulletins:
        if bulletin['url'] not in seen_urls:
            seen_urls.add(bulletin['url'])
            unique_bulletins.append(bulletin)
    
    logger.info(f"📊 Found {len(unique_bulletins)} unique {language} bulletins")
    return unique_bulletins

def process_audio_url(url, title, language, context_text):
    """Process and validate audio URL"""
    bulletins = []
    
    # Make URL absolute
    if not url.startswith('http'):
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = BASE_URL + url
        else:
            url = BASE_URL + '/' + url
    
    # Clean URL (remove query parameters if they cause issues)
    base_url = url.split('?')[0]
    
    if base_url.endswith('.mp3'):
        bulletin = {
            "url": base_url,
            "language": language,
            "title": title.strip() or f"{language.title()} Morning News",
            "filename": os.path.basename(base_url),
            "display_name": f"AIR_{language.upper()}_{datetime.now().strftime('%d%m%Y')}_{title[:30]}.mp3".replace(' ', '_').replace('/', '_'),
            "time": "Morning News",
            "date": datetime.now().strftime('%d-%m-%Y'),
            "source_page": "National Bulletins",
            "duration": 0,
            "context": context_text[:200]
        }
        bulletins.append(bulletin)
        logger.info(f"✅ Found: {bulletin['filename']}")
    
    return bulletins

# =============================================================================
# ✅ METHOD 2: Audio Archive Page Scraping
# =============================================================================
def fetch_from_audio_archive(language):
    """Fetch from audio archive search page"""
    session = get_session()
    
    try:
        response = session.get(AUDIO_ARCHIVE_URL, timeout=20)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for language tabs/buttons
        lang_tabs = soup.find_all('a', href=True, string=re.compile(language, re.I))
        
        bulletins = []
        
        # If we find language tabs, click through them (simulate by getting href)
        for tab in lang_tabs:
            tab_url = tab['href']
            if not tab_url.startswith('http'):
                tab_url = BASE_URL + tab_url
            
            try:
                tab_response = session.get(tab_url, timeout=20)
                if tab_response.status_code == 200:
                    tab_soup = BeautifulSoup(tab_response.text, 'html.parser')
                    
                    # Find audio links in this tab
                    for link in tab_soup.find_all('a', href=True):
                        if '.mp3' in link['href'].lower():
                            bulletins.extend(process_audio_url(
                                link['href'], 
                                link.get_text(), 
                                language,
                                ""
                            ))
            except:
                continue
        
        return bulletins
        
    except Exception as e:
        logger.error(f"Audio archive error: {e}")
        return []

# =============================================================================
# ✅ Check for 7:00-7:30 AM time slot - Simplified
# =============================================================================
def is_7am_time_slot(text):
    """
    Simple check for 7 AM related content
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Check for 7 AM indicators
    patterns = [
        r'7[\s:\.]*(00|05|10|15|20|25|30)',  # 7:00, 7.00, 7-00, etc.
        r'07[\s:\.]*(00|05|10|15|20|25|30)',
        r'morning[\s-]*7',
        r'7[\s-]*am',
        r'सात\s*बजे',
        r'प्रातः\s*7',
        r'सुबह\s*7',
        r'7\s*बजे'
    ]
    
    for pattern in patterns:
        if re.search(pattern, text_lower):
            # Exclude other times
            if not re.search(r'8[\s:]|9[\s:]|10[\s:]|11[\s:]|12[\s:]', text_lower):
                logger.info(f"✅ 7AM slot detected")
                return True
    
    return False

# =============================================================================
# ✅ Fetch English Morning News
# =============================================================================
def fetch_english_morning_news():
    """Fetch English morning news using multiple methods"""
    
    all_bulletins = []
    
    # Method 1: National Bulletins page
    logger.info("📡 Trying National Bulletins page...")
    bulletins = fetch_from_national_bulletins("english")
    all_bulletins.extend(bulletins)
    
    # Method 2: Audio Archive
    if not all_bulletins:
        logger.info("📡 Trying Audio Archive...")
        bulletins = fetch_from_audio_archive("english")
        all_bulletins.extend(bulletins)
    
    # Filter for 7 AM if possible, otherwise take latest
    filtered = []
    for bulletin in all_bulletins:
        full_text = f"{bulletin['title']} {bulletin.get('context', '')}"
        if is_7am_time_slot(full_text):
            filtered.append(bulletin)
            logger.info(f"✅ 7AM English: {bulletin['title']}")
    
    if not filtered and all_bulletins:
        logger.warning("⚠️ No 7AM specific, using latest bulletin")
        filtered = [all_bulletins[0]]
    
    return filtered

# =============================================================================
# ✅ Fetch Hindi Morning News
# =============================================================================
def fetch_hindi_morning_news():
    """Fetch Hindi morning news using multiple methods"""
    
    all_bulletins = []
    
    # Method 1: National Bulletins page
    logger.info("📡 Trying National Bulletins page...")
    bulletins = fetch_from_national_bulletins("hindi")
    all_bulletins.extend(bulletins)
    
    # Method 2: Audio Archive
    if not all_bulletins:
        logger.info("📡 Trying Audio Archive...")
        bulletins = fetch_from_audio_archive("hindi")
        all_bulletins.extend(bulletins)
    
    # Filter for 7 AM if possible, otherwise take latest
    filtered = []
    for bulletin in all_bulletins:
        full_text = f"{bulletin['title']} {bulletin.get('context', '')}"
        if is_7am_time_slot(full_text):
            filtered.append(bulletin)
            logger.info(f"✅ 7AM Hindi: {bulletin['title']}")
    
    if not filtered and all_bulletins:
        logger.warning("⚠️ No 7AM specific, using latest bulletin")
        filtered = [all_bulletins[0]]
    
    return filtered

# =============================================================================
# ✅ Get audio duration - Simplified
# =============================================================================
def get_audio_duration(file_path):
    """Simple file size based estimation"""
    try:
        # Try to use mutagen if available
        import mutagen
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        return audio.info.length
    except:
        # Fallback: estimate from file size (64kbps ~ 8KB/s)
        file_size = os.path.getsize(file_path)
        estimated_duration = file_size / (64 * 1024 / 8)  # 64kbps in bytes/sec
        return estimated_duration

def validate_audio_duration(file_path):
    """Basic validation"""
    duration = get_audio_duration(file_path)
    
    min_dur = getattr(Config, 'MIN_AUDIO_DURATION_SECONDS', 30)
    max_dur = getattr(Config, 'MAX_AUDIO_DURATION_SECONDS', 1800)
    
    if duration < min_dur:
        logger.warning(f"⚠️ Audio too short: {duration:.2f}s")
        return False, duration
    if duration > max_dur:
        logger.warning(f"⚠️ Audio too long: {duration:.2f}s")
        return False, duration
    
    logger.info(f"✅ Duration: {duration:.2f}s")
    return True, duration

# =============================================================================
# ✅ MAIN: Fetch Both Languages
# =============================================================================
def fetch_audio_bulletins():
    """Main function to fetch both English and Hindi bulletins"""
    result = {"english": None, "hindi": None}
    
    try:
        logger.info("=" * 60)
        logger.info("📡 FETCHING AIR MORNING NEWS")
        logger.info("=" * 60)
        
        # Fetch English
        logger.info("\n🇬🇧 ENGLISH NEWS")
        eng_list = fetch_english_morning_news()
        if eng_list:
            result["english"] = eng_list[0]
            logger.info(f"✅ Selected: {result['english']['title']}")
            logger.info(f"🔗 URL: {result['english']['url']}")
        
        # Fetch Hindi
        logger.info("\n🇮🇳 HINDI NEWS")
        hi_list = fetch_hindi_morning_news()
        if hi_list:
            result["hindi"] = hi_list[0]
            logger.info(f"✅ Selected: {result['hindi']['title']}")
            logger.info(f"🔗 URL: {result['hindi']['url']}")
        
        if not result["english"] and not result["hindi"]:
            logger.error("❌ No bulletins found")
        else:
            logger.info("\n✅ Bulletins fetched successfully")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return result

# =============================================================================
# ✅ DOWNLOAD AUDIO - Simplified
# =============================================================================
def download_audio(bulletin, max_retries=2):
    """Download audio file"""
    if not bulletin or not bulletin.get("url"):
        return None
    
    session = get_session()
    
    # Create directory
    os.makedirs(Config.AUDIO_DIR, exist_ok=True)
    
    # Clean filename
    filename = re.sub(r'[<>:"/\\|?*]', '', bulletin["display_name"])
    local_path = os.path.join(Config.AUDIO_DIR, filename)
    
    # Check if exists
    if os.path.exists(local_path):
        file_size = os.path.getsize(local_path)
        if file_size > 10240:  # >10KB
            logger.info(f"✅ Already exists: {filename}")
            return local_path
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",
        "Referer": BASE_URL + "/",
    }
    
    for attempt in range(max_retries):
        try:
            url = bulletin["url"]
            logger.info(f"⬇️ Downloading: {filename}")
            
            response = session.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            
            # Download
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                logger.info(f"✅ Downloaded: {file_size/1024:.1f}KB")
                return local_path
            
        except Exception as e:
            logger.error(f"❌ Attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return None

# =============================================================================
# ✅ MAIN EXECUTION
# =============================================================================
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    logger.info("🚀 AIR News Fetcher Started")
    logger.info("=" * 60)
    
    # Fetch bulletins
    result = fetch_audio_bulletins()
    
    # Download
    if result.get("english"):
        path = download_audio(result["english"])
        if path:
            logger.info(f"💾 English saved: {path}")
    
    if result.get("hindi"):
        path = download_audio(result["hindi"])
        if path:
            logger.info(f"💾 Hindi saved: {path}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    if result["english"] or result["hindi"]:
        logger.info("✅ Process completed")
        
        # List files
        if os.path.exists(Config.AUDIO_DIR):
            files = [f for f in os.listdir(Config.AUDIO_DIR) if f.endswith('.mp3')]
            if files:
                logger.info(f"📁 Files in {Config.AUDIO_DIR}:")
                for f in files[-3:]:
                    logger.info(f"   • {f}")
    else:
        logger.error("❌ No news found")
        logger.info("💡 Try visiting: https://www.newsonair.gov.in/national-bulletins/")
    
    logger.info("\n✨ Done")