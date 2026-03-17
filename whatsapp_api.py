import requests
import logging
import os
import time
from config import Config

logger = logging.getLogger(__name__)

class WhatsAppCloudAPI:
    def __init__(self):
        self.phone_number_id = str(Config.WHATSAPP_PHONE_NUMBER_ID).strip()
        self.access_token = str(Config.WHATSAPP_ACCESS_TOKEN).strip()
        self.api_base = str(Config.WHATSAPP_API_BASE).strip().rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        self.media_endpoint = f"{self.api_base}/{self.phone_number_id}/media"
        self.messages_endpoint = f"{self.api_base}/{self.phone_number_id}/messages"
    
    def _clean_phone(self, phone):
        clean = ''.join(filter(str.isdigit, str(phone)))
        if clean.startswith('0'): clean = clean[1:]
        if not clean.startswith('91'): clean = '91' + clean
        return clean
    
    def test_connection(self, max_retries=3):
        for attempt in range(max_retries):
            try:
                resp = requests.get(f"{self.api_base}/{self.phone_number_id}", headers=self.headers, timeout=15)
                if resp.status_code == 200: return True
                time.sleep(2)
            except: time.sleep(2)
        return False
    
    def upload_media(self, file_path, mime_type="audio/mpeg"):
        try:
            if not os.path.exists(file_path): return False, "File not found"
            if os.path.getsize(file_path) > 16*1024*1024: return False, "File too large"
            
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, mime_type)}
                data = {"messaging_product": "whatsapp"}
                resp = requests.post(
                    self.media_endpoint,
                    headers={"Authorization": self.headers["Authorization"]},
                    files=files, data=data, timeout=180
                )
            
            if resp.status_code == 200:
                result = resp.json()
                media_id = result.get("id")
                if media_id: return True, media_id
            return False, resp.text
        except Exception as e:
            return False, str(e)
    
    def send_audio(self, phone, media_id):
        clean = self._clean_phone(phone)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean,
            "type": "audio",
            "audio": {"id": media_id}
        }
        try:
            resp = requests.post(self.messages_endpoint, headers=self.headers, json=payload, timeout=60)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.text
        except Exception as e:
            return False, str(e)
    
    def send_audio_file_direct(self, phone, file_path):
        """
        ✅ SEND DIRECT AUDIO FILE via WhatsApp
        Uploads local file and sends as audio attachment
        """
        try:
            success, result = self.upload_media(file_path)
            if not success:
                return False, result
            
            media_id = result if isinstance(result, str) else result.get("id")
            return self.send_audio(phone, media_id)
        except Exception as e:
            logger.error(f"❌ Direct audio send error: {e}")
            return False, str(e)
    
    def send_text(self, phone, text):
        clean = self._clean_phone(phone)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean,
            "type": "text",
            "text": {"body": text}
        }
        try:
            resp = requests.post(self.messages_endpoint, headers=self.headers, json=payload, timeout=30)
            return resp.status_code == 200, resp.text
        except Exception as e:
            return False, str(e)