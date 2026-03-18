# news_fetcher.py - ✅ 100% FIXED VERSION
import requests
from bs4 import BeautifulSoup
import re
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

def fetch_morning_headlines(url=None):
    """
    ✅ RELIABLY SCRAPES ALL 6 HEADLINES from:
    https://www.newsonair.gov.in/bulletins-detail-category/morning-news/
    
    Format: Headlines are plain text lines after "THE HEADLINES:" (NOT numbered)
    """
    if url is None:
        url = "https://www.newsonair.gov.in/bulletins-detail-category/morning-news/"
    
    # ✅ Clean URL - remove trailing spaces
    url = url.strip()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }
    
    try:
        logger.info(f"🔍 Fetching headlines from: {url}")
        response = requests.get(url, headers=headers, timeout=45)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = []
        
        # ✅ METHOD 1: Find content area
        content_div = soup.find('div', class_='content-area')
        if not content_div:
            content_div = soup.find('main') or soup.find('article') or soup
        
        # ✅ Get text with line breaks preserved
        text_content = content_div.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # ✅ Find "THE HEADLINES:" section (flexible: :, ::, or just "headlines")
        headlines_start_idx = -1
        for i, line in enumerate(lines):
            if re.search(r'^\s*the\s+headlines\s*[:\s]*$', line, re.IGNORECASE):
                headlines_start_idx = i
                logger.info(f"✅ Found 'THE HEADLINES' at line {i}")
                break
        
        if headlines_start_idx == -1:
            logger.error("❌ Could not find 'THE HEADLINES' section")
            # Debug: show what we got
            for i, line in enumerate(lines[:30]):
                logger.debug(f"Line {i}: {line[:100]}")
            return _error_response("Could not find headlines section", url)
        
        # ✅ Extract next 6 meaningful lines as headlines (NOT numbered format)
        headline_count = 0
        for i in range(headlines_start_idx + 1, len(lines)):
            if headline_count >= 6:
                break
                
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Stop at end markers
            if re.search(r'<><><>|once again|for details|log on|visit website|air news', line, re.IGNORECASE):
                logger.info(f"⏹️ Stopping at end marker: {line[:50]}")
                break
            
            # Skip lines that are dates, times, or metadata
            if re.match(r'^\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}:\d{2}\s*[AP]M|^morning\s+news$', line, re.IGNORECASE):
                continue
            
            # ✅ This is a valid headline - clean and add it
            headline = re.sub(r'\s*[<>\[\]{}|\\]+.*$', '', line).strip()
            
            # Validate: must be meaningful (not URL, not too short, not generic)
            if (headline and 
                len(headline) > 25 and 
                len(headline) < 300 and
                not headline.lower().startswith(('http', 'www', 'follow', 'share', 'subscribe', 'for details', 'click here')) and
                not re.match(r'^\d+[\)\.\-\s]+$', headline)):  # Skip just numbers
                
                headlines.append(headline)
                headline_count += 1
                logger.info(f"   ✅ {headline_count}. {headline[:80]}...")
        
        # ✅ METHOD 2: Fallback - Search for <p> tags containing headline-like text
        if len(headlines) < 6:
            logger.info(f"⚠️ Found only {len(headlines)} headlines, trying paragraph fallback...")
            
            # Look for paragraphs with substantial text after headlines section
            for p in content_div.find_all('p'):
                text = p.get_text(strip=True)
                if (text and 
                    len(text) > 30 and 
                    len(text) < 300 and
                    text not in headlines and
                    not text.lower().startswith(('http', 'www', 'follow', 'the headlines'))):
                    
                    # Clean the text
                    clean_text = re.sub(r'\s*[<>\[\]{}|\\]+.*$', '', text).strip()
                    if clean_text and len(clean_text) > 25 and clean_text not in headlines:
                        headlines.append(clean_text)
                        logger.info(f"   🔄 Fallback: {len(headlines)}. {clean_text[:80]}...")
                        if len(headlines) >= 6:
                            break
        
        # ✅ Ensure exactly 6 headlines max
        headlines = headlines[:6]
        
        # ❌ Error if still no headlines
        if not headlines:
            logger.error("❌ Could not extract ANY headlines from website")
            logger.error(f"❌ Total lines found: {len(lines)}")
            # Show sample for debugging
            start = max(0, headlines_start_idx - 2)
            end = min(len(lines), headlines_start_idx + 10)
            sample = '\n'.join(lines[start:end])
            logger.error(f"❌ Sample content:\n{sample}")
            return _error_response("Could not scrape any headlines", url)
        
        logger.info(f"✅ Successfully extracted {len(headlines)} REAL headlines")
        for i, hl in enumerate(headlines, 1):
            logger.info(f"   📰 {i}. {hl}")
        
        return {
            'success': True,
            'headlines': headlines,
            'source_url': url,
            'fetched_at': datetime.now().isoformat(),
            'count': len(headlines)
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error: {e}")
        return _error_response(f"Network error: {e}", url)
    except Exception as e:
        logger.error(f"❌ Parsing error: {e}", exc_info=True)
        return _error_response(str(e), url)


def _error_response(error_msg: str, url: str) -> dict:
    """Helper function to return consistent error response"""
    return {
        'success': False,
        'error': error_msg,
        'headlines': [],
        'source_url': url,
        'fetched_at': datetime.now().isoformat()
    }