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
        self.api_base = str(Config.WHATSAPP_API_BASE).strip()
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        self.media_endpoint = f"{self.api_base}/{self.phone_number_id}/media"
        self.messages_endpoint = f"{self.api_base}/{self.phone_number_id}/messages"

    def upload_media_to_whatsapp(self, file_path, mime_type="audio/mpeg"):
        try:
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}"
            
            file_size = os.path.getsize(file_path)
            if file_size > 16 * 1024 * 1024:
                return False, "File exceeds 16MB limit"
            
            logger.info(f"📤 Uploading to WhatsApp: {os.path.basename(file_path)}")
            
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, mime_type)}
                data = {"messaging_product": "whatsapp"}
                
                response = requests.post(self.media_endpoint, headers=self.headers, files=files, data=data, timeout=120)
                
            if response.status_code == 200:
                result = response.json()
                media_id = result.get("id")
                if media_id:
                    logger.info(f"✅ Media uploaded: {media_id}")
                    return True, media_id
            logger.error(f"❌ Upload failed: {response.text}")
            return False, response.text
        except Exception as e:
            logger.error(f"❌ Upload exception: {e}")
            return False, str(e)

    def send_audio_message(self, phone_number, media_id):
        clean_phone = self._clean_phone_number(phone_number)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "audio",
            "audio": {"id": media_id}
        }
        try:
            response = requests.post(self.messages_endpoint, headers=self.headers, json=payload, timeout=60)
            if response.status_code == 200:
                logger.info(f"✅ Audio sent to {clean_phone}")
                return True, response.json()
            logger.error(f"❌ Send failed: {response.text}")
            return False, response.text
        except Exception as e:
            return False, str(e)

    def send_text_message(self, phone_number, text):
        clean_phone = self._clean_phone_number(phone_number)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"body": text}
        }
        try:
            response = requests.post(self.messages_endpoint, headers=self.headers, json=payload, timeout=30)
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def _clean_phone_number(self, phone_number):
        clean = str(phone_number).replace("+", "").replace(" ", "").strip()
        if not clean.startswith("91"): clean = "91" + clean
        return clean

    def _send_audio_with_upload(self, phone_number, audio_source, is_local_path=False):
        temp_path = None
        try:
            if is_local_path:
                temp_path = audio_source
            else:
                # Download if URL provided
                resp = requests.get(audio_source, timeout=120)
                temp_path = os.path.join(Config.AUDIO_DIR, f"tmp_{int(time.time())}.mp3")
                with open(temp_path, "wb") as f: f.write(resp.content)
            
            success, media_id = self.upload_media_to_whatsapp(temp_path)
            if success:
                return self.send_audio_message(phone_number, media_id)
            return False, media_id
        except Exception as e:
            return False, str(e)
        finally:
            if not is_local_path and temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    def test_connection(self):
        try:
            url = f"{self.api_base}/{self.phone_number_id}"
            resp = requests.get(url, headers=self.headers, timeout=10)
            return resp.status_code == 200
        except:
            return False