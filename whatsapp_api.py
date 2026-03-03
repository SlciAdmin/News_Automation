import requests
import logging
import os
import time
from config import Config

logger = logging.getLogger(__name__)

class WhatsAppCloudAPI:
    def __init__(self):
        # Strip whitespace from all config values
        self.phone_number_id = str(Config.WHATSAPP_PHONE_NUMBER_ID).strip()
        self.access_token = str(Config.WHATSAPP_ACCESS_TOKEN).strip()
        self.api_base = str(Config.WHATSAPP_API_BASE).strip()
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        self.media_endpoint = f"{self.api_base}/{self.phone_number_id}/media"
        self.messages_endpoint = f"{self.api_base}/{self.phone_number_id}/messages"
    
    def upload_media_to_whatsapp(self, file_path, mime_type="audio/mpeg"):
        """
        Upload audio file to WhatsApp Cloud API
        Returns: (success: bool, media_id_or_error: str)
        """
        try:
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}"
            
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # WhatsApp limits
            MAX_AUDIO_SIZE = 16 * 1024 * 1024  # 16MB
            if file_size > MAX_AUDIO_SIZE:
                logger.error(f"❌ File too large: {file_size/1024/1024:.2f}MB (max 16MB)")
                return False, f"File exceeds 16MB limit"
            
            logger.info(f"📤 Uploading to WhatsApp: {filename} ({file_size} bytes)")
            
            with open(file_path, "rb") as f:
                files = {
                    "file": (filename, f, mime_type)
                }
                data = {
                    "messaging_product": "whatsapp"
                }
                
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                }
                
                response = requests.post(
                    self.media_endpoint,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120
                )
            
            if response.status_code == 200:
                result = response.json()
                media_id = result.get("id")
                if media_id:
                    logger.info(f"✅ Media uploaded successfully: {media_id}")
                    return True, media_id
                else:
                    logger.error(f"❌ No media_id in response: {result}")
                    return False, f"No media_id: {result}"
            else:
                error_text = response.text[:500] if response.text else "No response"
                logger.error(f"❌ Upload failed [{response.status_code}]: {error_text}")
                
                try:
                    error_json = response.json()
                    if "error" in error_json:
                        error_msg = error_json["error"].get("message", "Unknown error")
                        return False, f"WhatsApp error: {error_msg}"
                except:
                    pass
                
                return False, f"HTTP {response.status_code}: {error_text}"
                
        except requests.exceptions.Timeout:
            logger.error("❌ Upload timeout")
            return False, "Upload timeout"
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection error")
            return False, "Connection error"
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            return False, f"Error: {str(e)}"
    
    def send_audio_message(self, phone_number, media_id):
        """Send audio message using media_id"""
        clean_phone = self._clean_phone_number(phone_number)
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "audio",
            "audio": {"id": media_id}
        }
        
        try:
            logger.debug(f"📤 Sending audio to {clean_phone} | media_id: {media_id}")
            
            response = requests.post(
                self.messages_endpoint,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                msg_id = result.get("messages", [{}])[0].get("id", "unknown")
                logger.info(f"✅ Audio sent to {clean_phone}: {msg_id}")
                return True, result
            else:
                error_text = response.text[:500] if response.text else "No response"
                logger.error(f"❌ Send failed [{response.status_code}]: {error_text}")
                
                try:
                    error_json = response.json()
                    if "error" in error_json:
                        error_msg = error_json["error"].get("message", "Unknown error")
                        return False, f"WhatsApp error: {error_msg}"
                except:
                    pass
                
                return False, f"Send failed: {response.status_code}"
                
        except Exception as e:
            logger.error(f"❌ Exception sending audio: {e}")
            return False, str(e)
    
    def send_text_message(self, phone_number, text):
        """Send plain text message"""
        clean_phone = self._clean_phone_number(phone_number)
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"body": text}
        }
        
        try:
            response = requests.post(
                self.messages_endpoint,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                msg_id = result.get("messages", [{}])[0].get("id", "unknown")
                logger.debug(f"📝 Text sent to {clean_phone}: {msg_id}")
                return True, result
            else:
                logger.warning(f"⚠️ Text send failed [{response.status_code}]")
                return False, response.text if response.text else f"HTTP {response.status_code}"
                
        except Exception as e:
            logger.warning(f"⚠️ Text exception: {e}")
            return False, str(e)
    
    def _clean_phone_number(self, phone_number):
        """Clean phone number to standard format"""
        clean = str(phone_number).replace("+", "").replace("whatsapp:", "").replace(" ", "").strip()
        if not clean.startswith("91"):
            clean = "91" + clean
        return clean
    
    def _send_audio_with_upload(self, phone_number, audio_source, is_local_path=False):
        """
        Upload audio to WhatsApp and send
        audio_source: either URL or local file path
        """
        temp_path = None
        try:
            if is_local_path:
                logger.info(f"📁 Using local file: {audio_source}")
                if not os.path.exists(audio_source):
                    return False, f"Local file not found: {audio_source}"
                temp_path = audio_source
            else:
                logger.info(f"⬇️ Downloading from URL: {audio_source}")
                resp = requests.get(
                    audio_source,
                    timeout=120,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                resp.raise_for_status()
                
                temp_path = os.path.join(Config.AUDIO_DIR, f"tmp_{int(time.time())}.mp3")
                with open(temp_path, "wb") as f:
                    f.write(resp.content)
                
                if not os.path.exists(temp_path):
                    return False, "File not found after download"
                
                file_size = os.path.getsize(temp_path)
                if file_size < 1000:
                    return False, f"File too small: {file_size} bytes"
                
                logger.info(f"📊 File size: {file_size/1024:.2f} KB")
            
            # Upload to WhatsApp
            success, media_id_or_err = self.upload_media_to_whatsapp(temp_path, "audio/mpeg")
            if not success:
                logger.error(f"❌ Upload failed: {media_id_or_err}")
                return False, media_id_or_err
            
            # Send audio message
            return self.send_audio_message(phone_number, media_id_or_err)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Download error: {e}")
            return False, f"Download error: {str(e)}"
        except Exception as e:
            logger.error(f"❌ _send_audio_with_upload error: {e}", exc_info=True)
            return False, str(e)
        finally:
            if not is_local_path and temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"🧹 Cleaned up temp file: {temp_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete temp file: {e}")
    
    def test_connection(self):
        """Test API connectivity"""
        try:
            url = f"{self.api_base}/{self.phone_number_id}"
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            if resp.status_code == 200:
                logger.info("✅ WhatsApp API connected")
                return True
            else:
                logger.error(f"❌ Connection test failed [{resp.status_code}]: {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"❌ Connection exception: {e}")
            return False