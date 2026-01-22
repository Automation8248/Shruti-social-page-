import os
import requests
import sys
import re
import time
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
VIDEO_LIST_FILE = 'videos.txt'
HISTORY_FILE = 'history.txt'

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Public APIs (Agar ek fail ho to dusra try karega)
COBALT_INSTANCES = [
    "https://api.cobalt.tools",
    "https://cobalt.kwiatekmiki.pl",
    "https://cobalt.q1.si",
]

SEO_TAGS = ["#reels", "#trending", "#viral", "#explore", "#love", "#shayari"]
FORBIDDEN_WORDS = ["virtualaarvi", "aarvi", "video by", "uploaded by", "subscribe", "channel"]

# --- HELPER FUNCTIONS ---

def get_next_video():
    processed_urls = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            processed_urls = [line.strip() for line in f.readlines()]

    if not os.path.exists(VIDEO_LIST_FILE):
        print("❌ Error: videos.txt missing!")
        return None

    with open(VIDEO_LIST_FILE, 'r') as f:
        all_urls = [line.strip() for line in f.readlines() if line.strip()]

    for url in all_urls:
        if url not in processed_urls:
            return url
    return None

def is_text_safe(text):
    if not text: return False
    lower_text = text.lower()
    for word in FORBIDDEN_WORDS:
        if word in lower_text:
            return False
    return True

def translate_and_shorten(text):
    if not text or not text.strip(): return None
    try:
        translated = GoogleTranslator(source='auto', target='hi').translate(text)
        if is_text_safe(translated):
            words = translated.split()
            return " ".join(words[:5])
    except: pass
    
    if is_text_safe(text):
        words = text.split()
        return " ".join(words[:5])
    return "देखिए आज का वीडियो"

def download_via_cobalt(url):
    print(f"🔄 Trying to download via API (No Cookies Needed)...")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    payload = {
        "url": url,
        "videoQuality": "max",
        "filenamePattern": "basic"
    }

    download_url = None
    
    # Try different servers if one fails
    for instance in COBALT_INSTANCES:
        try:
            print(f"📡 Connecting to: {instance}")
            api_url = f"{instance}/api/json"
            resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                if 'url' in data:
                    download_url = data['url']
                    print("✅ Video Link Found!")
                    break
            elif resp.status_code == 429:
                print("⚠️ Server busy, trying next...")
                continue
        except Exception as e:
            print(f"⚠️ Error on {instance}: {e}")
            continue
            
    if not download_url:
        print("❌ All APIs failed to fetch video.")
        return None

    # Now download the actual file
    try:
        file_resp = requests.get(download_url, stream=True)
        filename = "final_video.mp4"
        with open(filename, 'wb') as f:
            for chunk in file_resp.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
        return filename
    except Exception as e:
        print(f"❌ File Save Error: {e}")
        return None

def process_video(url):
    # 1. Download Video
    filename = download_via_cobalt(url)
    if not filename: return None

    # 2. Generate Basic Data (Since we are not scraping metadata heavily)
    # API metadata nahi deta, to hum generic use karenge
    hindi_text = "✨ देखिए आज का शानदार वीडियो! ❤️"
    hashtags = "#reels #trending #viral #explore #instagram " + " ".join(SEO_TAGS[:3])

    return {
        "filename": filename,
        "title": "Instagram Reel",
        "hindi_text": hindi_text,
        "hashtags": hashtags,
        "original_url": url
    }

def upload_to_catbox(filepath):
    print("🚀 Uploading to Catbox...")
    try:
        with open(filepath, "rb") as f:
            response = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": f}, timeout=60)
            if response.status_code == 200:
                return response.text.strip()
    except: pass
    return None

def send_notifications(video_data, catbox_url):
    print("\n--- Sending Notifications ---")
    tg_caption = f"{video_data['hindi_text']}\n.\n.\n{video_data['hashtags']}"
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("📤 Telegram Video Sending...")
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        try:
            with open(video_data['filename'], 'rb') as video_file:
                payload = {"chat_id": str(TELEGRAM_CHAT_ID), "caption": tg_caption, "parse_mode": "Markdown"}
                files = {'video': video_file}
                requests.post(tg_url, data=payload, files=files, timeout=60)
                print("✅ Telegram Sent!")
        except Exception as e: print(f"❌ Telegram Error: {e}")

    if WEBHOOK_URL and catbox_url:
        print(f"📤 Webhook Sending...")
        payload = {"content": tg_caption, "video_url": catbox_url}
        try: requests.post(WEBHOOK_URL, json=payload, timeout=30)
        except: pass

def update_history(url):
    with open(HISTORY_FILE, 'a') as f: f.write(url + '\n')

if __name__ == "__main__":
    next_url = get_next_video()
    if not next_url:
        print("💤 No new videos.")
        sys.exit(0)
    
    data = process_video(next_url)
    
    if data and data['filename']:
        catbox_link = upload_to_catbox(data['filename'])
        send_notifications(data, catbox_link)
        update_history(next_url)
        if os.path.exists(data['filename']): os.remove(data['filename'])
        print("✅ Task Completed.")
    else:
        print("❌ Task Failed.")
        sys.exit(1)
