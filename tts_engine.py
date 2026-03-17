import asyncio
import edge_tts
import os
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class TTSEngine:
    """
    ✅ Human-like TTS using Microsoft Azure Neural Voices (FREE)
    English: en-US-AriaNeural | Hindi: hi-IN-SwaraNeural
    """
    
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or Config.TTS_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        self.en_voice = Config.TTS_ENGLISH_VOICE
        self.hi_voice = Config.TTS_HINDI_VOICE
        self.rate = Config.TTS_RATE
        self.volume = Config.TTS_VOLUME
        self.pitch = Config.TTS_PITCH
    
    async def _generate(self, text: str, voice: str, output_path: str) -> bool:
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch
            )
            await communicate.save(output_path)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 500:
                logger.info(f"✅ TTS: {output_path} ({os.path.getsize(output_path)/1024:.1f} KB)")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return False
    
    def generate_headlines_audio(self, headlines: list, language: str = 'en') -> str:
        """Generate SINGLE audio file from 6 headlines"""
        if not headlines:
            return None
        
        # Format as news bulletin
        if language == 'en':
            bulletin = "Good morning. Today's top six headlines. "
            for i, hl in enumerate(headlines[:6], 1):
                bulletin += f"Headline {i}: {hl}. "
            bulletin += "Thank you for listening to AIR Morning News."
        else:
            bulletin = "सुप्रभात। आज की छह प्रमुख सुर्खियाँ। "
            for i, hl in enumerate(headlines[:6], 1):
                bulletin += f"सुर्खी {i}: {hl}. "
            bulletin += "एआईआर मॉर्निंग न्यूज़ सुनने के लिए धन्यवाद।"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"headlines_6_{language}_{timestamp}.mp3"
        output_path = os.path.join(self.output_dir, filename)
        
        voice = self.en_voice if language == 'en' else self.hi_voice
        
        try:
            success = asyncio.run(self._generate(bulletin, voice, output_path))
            return output_path if success and os.path.exists(output_path) else None
        except Exception as e:
            logger.error(f"❌ TTS failed: {e}")
            return None
    
    def generate_both_languages(self, headlines: list) -> dict:
        """Generate audio in BOTH English and Hindi"""
        result = {}
        en_path = self.generate_headlines_audio(headlines, 'en')
        hi_path = self.generate_headlines_audio(headlines, 'hi')
        if en_path: result['en'] = en_path
        if hi_path: result['hi'] = hi_path
        return result