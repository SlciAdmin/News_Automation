#!/usr/bin/env python3
"""Comprehensive debug script for WhatsApp API issues"""
import os
import sys
import json
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

def debug_whatsapp_config():
    """Check WhatsApp configuration for common issues"""
    print("🔍 DEBUGGING WHATSAPP CONFIGURATION")
    print("=" * 60)
    
    # Check for trailing spaces
    phone_id = Config.WHATSAPP_PHONE_NUMBER_ID
    token = Config.WHATSAPP_ACCESS_TOKEN
    api_base = Config.WHATSAPP_API_BASE
    
    print(f"\n📱 Phone Number ID:")
    print(f"   Value: '{phone_id}'")
    print(f"   Length: {len(str(phone_id))}")
    print(f"   Has trailing spaces: {str(phone_id).strip() != str(phone_id)}")
    
    print(f"\n🔑 Access Token:")
    print(f"   Starts with: '{str(token)[:20]}...'")
    print(f"   Length: {len(str(token))}")
    print(f"   Has trailing spaces: {str(token).strip() != str(token)}")
    
    print(f"\n🌐 API Base URL:")
    print(f"   Value: '{api_base}'")
    print(f"   Length: {len(str(api_base))}")
    print(f"   Has trailing spaces: {str(api_base).strip() != str(api_base)}")
    
    # Test direct API call
    print(f"\n🔗 Testing direct API call...")
    headers = {
        "Authorization": f"Bearer {str(token).strip()}"
    }
    
    url = f"{str(api_base).strip()}/{str(phone_id).strip()}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ API call successful!")
            data = response.json()
            print(f"   Business name: {data.get('name', 'N/A')}")
        else:
            print(f"   ❌ API call failed")
            try:
                error = response.json()
                print(f"   Error: {json.dumps(error, indent=2)}")
            except:
                print(f"   Response: {response.text[:200]}")
                
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print("\n" + "=" * 60)
    
    # Check token permissions
    print("\n🔐 Checking token permissions...")
    url = "https://graph.facebook.com/debug_token"
    params = {
        "input_token": str(token).strip(),
        "access_token": str(token).strip()
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                scopes = data["data"].get("scopes", [])
                print(f"   Token is valid: {data['data'].get('is_valid', False)}")
                print(f"   App ID: {data['data'].get('app_id', 'N/A')}")
                print(f"   Expires at: {data['data'].get('expires_at', 'N/A')}")
                print(f"\n   Permissions: {', '.join(scopes[:10])}")
                
                if "whatsapp_business_messaging" not in scopes:
                    print("   ⚠️ Missing 'whatsapp_business_messaging' permission!")
                if "business_management" not in scopes:
                    print("   ⚠️ Missing 'business_management' permission!")
            else:
                print(f"   Unexpected response: {data}")
        else:
            print(f"   Failed to check token: {response.status_code}")
    except Exception as e:
        print(f"   Error checking token: {e}")
    
    return

def check_phone_number_format():
    """Check if phone numbers in database are properly formatted"""
    print("\n📞 Checking phone number format in database...")
    try:
        import database
        subs = database.get_active_subscribers()
        print(f"   Found {len(subs)} active subscribers")
        
        for sub in subs:
            phone = sub['phone_number']
            print(f"   - {phone} (format: {'✅' if phone.startswith('91') else '❌ no country code'})")
            
    except Exception as e:
        print(f"   Error checking database: {e}")

if __name__ == "__main__":
    debug_whatsapp_config()
    check_phone_number_format()
    
    print("\n💡 RECOMMENDATIONS:")
    print("1. Make sure your test number has messaged your business within last 24h")
    print("2. Verify all config values have NO trailing spaces")
    print("3. Check that your access token has 'whatsapp_business_messaging' permission")
    print("4. Ensure phone numbers in database start with '91' (India)")