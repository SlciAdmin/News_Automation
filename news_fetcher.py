import requests
from bs4 import BeautifulSoup
import re
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

def fetch_morning_headlines(url=None):
    """
    ✅ SCRAPES REAL HEADLINES from:
    https://www.newsonair.gov.in/bulletins-detail-category/morning-news/
    
    Returns ONLY the 6 headlines from "THE HEADLINES ::" section
    """
    if url is None:
        url = "https://www.newsonair.gov.in/bulletins-detail-category/morning-news/"
    
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
        
        # ✅ METHOD 1: Find content by class and extract headlines
        content_div = soup.find('div', class_='content-area')
        if not content_div:
            content_div = soup.find('main') or soup.find('article') or soup
        
        # Get raw text with line breaks preserved
        text_content = content_div.get_text(separator='\n', strip=True)
        
        # Debug: Log first 500 chars to see structure
        logger.debug(f"Content preview: {text_content[:500]}")
        
        # ✅ Find "THE HEADLINES ::" section (case-insensitive, flexible spacing)
        lines = text_content.split('\n')
        in_headlines = False
        count = 0
        
        for line in lines:
            line = line.strip()
            
            # Detect headlines section start (flexible matching)
            if re.search(r'the\s*headlines\s*::', line, re.IGNORECASE):
                in_headlines = True
                logger.info("✅ Found 'THE HEADLINES ::' section")
                continue
            
            if in_headlines and count < 6:
                # ✅ Match numbered headlines: "1. Text" or "1) Text" or "1 - Text"
                match = re.match(r'^[\(\s]*\d+[\)\.\-\s]+\s*(.+)$', line)
                if match:
                    hl = match.group(1).strip()
                    # Clean up markers like <><><>
                    hl = re.sub(r'\s*[<>\[\]]+.*$', '', hl).strip()
                    
                    # Validate: must be meaningful text
                    if hl and len(hl) > 25 and not hl.lower().startswith(('http', 'www', 'follow', 'share')):
                        headlines.append(hl)
                        count += 1
                        logger.info(f"   {count}. {hl[:70]}...")
                
                # Stop if we hit end marker or unrelated content
                elif line and count > 0:
                    if re.search(r'<><><>|once again|for details|log on', line, re.IGNORECASE):
                        break
        
        # ✅ METHOD 2: Fallback - Search for <p> tags with numbered content
        if not headlines:
            logger.info("⚠️ Method 1 failed, trying paragraph search...")
            for p in content_div.find_all('p'):
                text = p.get_text(strip=True)
                # Match: "1. Headline" pattern
                match = re.match(r'^[\(\s]*\d+[\)\.\-\s]+\s*(.+)$', text)
                if match:
                    hl = match.group(1).strip()
                    hl = re.sub(r'\s*[<>\[\]]+.*$', '', hl).strip()
                    if hl and len(hl) > 25:
                        headlines.append(hl)
                        if len(headlines) >= 6:
                            break
        
        # ✅ METHOD 3: Final fallback - Search entire page for numbered patterns
        if not headlines:
            logger.info("⚠️ Method 2 failed, trying full page scan...")
            # Find all text that looks like "1. Something long"
            pattern = r'[\(\s]*\d+[\)\.\-\s]+\s*([A-Z][^.]{30,200}\.)'
            matches = re.findall(pattern, text_content)
            for m in matches:
                hl = m.strip()
                hl = re.sub(r'\s*[<>\[\]]+.*$', '', hl).strip()
                if hl and len(hl) > 25:
                    headlines.append(hl)
                    if len(headlines) >= 6:
                        break
        
        # ✅ Ensure max 6 headlines
        headlines = headlines[:6]
        
        # ❌ NO DUMMY: Return error if no headlines found
        if not headlines:
            logger.error("❌ Could not extract headlines from website")
            logger.error(f"❌ Content length: {len(text_content)} chars")
            # Log sample for debugging
            sample = text_content[text_content.lower().find('headlines')-50:text_content.lower().find('headlines')+200]
            logger.error(f"❌ Sample around 'headlines': {sample}")
            return {
                'success': False,
                'error': 'Could not scrape headlines - website structure may have changed',
                'headlines': [],
                'source_url': url,
                'fetched_at': datetime.now().isoformat()
            }
        
        logger.info(f"✅ Successfully extracted {len(headlines)} REAL headlines")
        return {
            'success': True,
            'headlines': headlines,
            'source_url': url,
            'fetched_at': datetime.now().isoformat()
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error: {e}")
        return {
            'success': False,
            'error': f'Network error: {e}',
            'headlines': []
        }
    except Exception as e:
        logger.error(f"❌ Parsing error: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'headlines': []
        }