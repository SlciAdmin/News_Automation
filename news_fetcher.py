# news_fetcher.py - ✅ FULLY WORKING VERSION
import requests
from bs4 import BeautifulSoup
import re
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

def fetch_morning_headlines(url=None):
    """
    ✅ SCRAPES HEADLINES FROM newsonair.gov.in
    Handles: THE HEADLINES:- format with numbered list
    """
    if url is None:
        url = "https://www.newsonair.gov.in/bulletins-detail-category/morning-news/"
    
    url = url.strip()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
        'Connection': 'keep-alive',
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
        
        # ✅ Get all text with line breaks
        text_content = content_div.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # ✅ DEBUG: Show first 30 lines to understand structure
        logger.info("📋 First 30 lines of content:")
        for i, line in enumerate(lines[:30]):
            logger.debug(f"Line {i}: {line}")
        
        # ✅ Find "THE HEADLINES" section (flexible pattern)
        headlines_start_idx = -1
        for i, line in enumerate(lines):
            # Match: "THE HEADLINES:", "THE HEADLINES:-", "THE HEADLINES"
            if re.search(r'the\s+headlines\s*[:\-]*', line, re.IGNORECASE):
                headlines_start_idx = i
                logger.info(f"✅ Found headlines marker at line {i}: '{line}'")
                break
        
        if headlines_start_idx == -1:
            logger.error("❌ Could not find 'THE HEADLINES' section")
            return _error_response("Could not find headlines section", url)
        
        # ✅ Extract numbered headlines (1., 2., 3., etc.)
        headline_count = 0
        for i in range(headlines_start_idx + 1, len(lines)):
            if headline_count >= 6:
                break
                
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Stop at end markers
            if re.search(r'<<<<<|>>>>>|once again|for details|log on|visit website', line, re.IGNORECASE):
                logger.info(f"⏹️ Stopping at marker: {line[:50]}")
                break
            
            # ✅ Match numbered headlines: "1. Headline text" or "2. Headline text"
            numbered_match = re.match(r'^\d+\.\s+(.+)$', line)
            if numbered_match:
                headline = numbered_match.group(1).strip()
                
                # Validate headline
                if (headline and 
                    len(headline) > 20 and 
                    len(headline) < 400 and
                    not headline.lower().startswith(('http', 'www', 'follow'))):
                    
                    headlines.append(headline)
                    headline_count += 1
                    logger.info(f"   ✅ {headline_count}. {headline[:100]}...")
            
            # Also try to catch unnumbered lines that look like headlines
            elif (headline_count > 0 and headline_count < 6 and
                  len(line) > 30 and 
                  len(line) < 400 and
                  not line.lower().startswith(('http', 'www', 'prime minister', 'external affairs'))):
                # This might be a continuation or unnumbered headline
                if not any(line in h for h in headlines):
                    headlines.append(line)
                    headline_count += 1
                    logger.info(f"    {headline_count}. {line[:100]}...")
        
        # ✅ METHOD 2: Fallback - Try finding <ol> or <ul> lists
        if len(headlines) < 6:
            logger.info(f"⚠️ Found only {len(headlines)} headlines, trying list fallback...")
            
            # Look for ordered lists
            for ol in content_div.find_all(['ol', 'ul']):
                for li in ol.find_all('li'):
                    text = li.get_text(strip=True)
                    if (text and 
                        len(text) > 20 and 
                        len(text) < 400 and
                        text not in headlines and
                        not text.lower().startswith(('http', 'www'))):
                        
                        # Remove leading numbers if present
                        text = re.sub(r'^\d+\.\s*', '', text).strip()
                        headlines.append(text)
                        logger.info(f"   🔄 List item: {text[:100]}...")
                        if len(headlines) >= 6:
                            break
                if len(headlines) >= 6:
                    break
        
        # ✅ METHOD 3: Last resort - Find paragraphs after headlines marker
        if len(headlines) < 6:
            logger.info(f"⚠️ Trying paragraph extraction...")
            
            # Find the headlines section in HTML
            headline_section = None
            for element in content_div.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'strong', 'b']):
                if re.search(r'the\s+headlines', element.get_text(), re.IGNORECASE):
                    headline_section = element
                    break
            
            if headline_section:
                # Get next sibling elements
                current = headline_section.next_sibling
                count = 0
                while current and count < 10:
                    if hasattr(current, 'name') and current.name in ['p', 'li']:
                        text = current.get_text(strip=True)
                        # Remove leading numbers
                        text = re.sub(r'^\d+\.\s*', '', text).strip()
                        if (text and 
                            len(text) > 30 and 
                            len(text) < 400 and
                            text not in headlines):
                            headlines.append(text)
                            logger.info(f"   📄 Paragraph: {text[:100]}...")
                    current = current.next_sibling if hasattr(current, 'next_sibling') else None
                    count += 1
        
        # ✅ Limit to 6 headlines
        headlines = headlines[:6]
        
        # ❌ Error if no headlines
        if not headlines:
            logger.error("❌ Could not extract ANY headlines")
            return _error_response("Could not scrape any headlines", url)
        
        logger.info(f"✅ Successfully extracted {len(headlines)} headlines")
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