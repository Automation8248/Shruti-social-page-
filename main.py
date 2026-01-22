import os
import requests
import sys
import time
import instaloader
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
VIDEO_LIST_FILE = 'videos.txt'
HISTORY_FILE = 'history.txt'

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

SEO_TAGS = ["#reels", "#trending", "#viral", "#explore", "#love", "#shayari"]

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

def translate_text(text):
    if not text: return "✨ New Reel"
    try:
        translated = GoogleTranslator(source='auto', target='hi').translate(text)
        return " ".join(translated.split()[:6])
    except:
        return "✨ New Reel"

def download_instagram_video(url):
    print(f"🔄 Trying to download using Instaloader: {url}")
    
    # Shortcode nikalo URL se
    try:
        if "/reel/" in url:
            shortcode = url.split("/reel/")[1].split("/")[0]
        elif "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        else:
            print("❌ Invalid URL format")
            return None
    except:
        print("❌ Could not parse URL")
        return None

    # Instaloader Setup
    L = instaloader.Instaloader()
    
    # AGAR YE FAIL HOTA HAI TO SIRF COOKIES HI BACHA SAKTI HAIN
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Video URL mil gaya
        video_url = post.video_url
        caption = post.caption
        
        if not video_url:
            print("❌ No video found in post.")
            return None

        print("⬇️ Downloading video file...")
        response = requests.get(video_url, stream=True)
        filename = "final_video.mp4"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
                
        return {
            "filename": filename,
            "caption": caption,
            "shortcode": shortcode
        }

    except Exception as e:
        print(f"❌ Instaloader Error: {e}")
        print("⚠️ GitHub Server IP is heavily blocked by Instagram.")
        return None

def process_video(url):
    data = download_instagram_video(url)
    if not data: return None

    # Processing Text
    hindi_text = translate_text(data['caption'])
    hashtags = "#reels #trending " + " ".join(SEO_TAGS[:3])

    return {
        "filename": data['filename'],
        "title": f"Reel {data['shortcode']}",
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
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        try:
            with open(video_data['filename'], 'rb') as video_file:
                payload = {"chat_id": str(TELEGRAM_CHAT_ID), "caption": tg_caption, "parse_mode": "Markdown"}
                files = {'video': video_file}
                requests.post(tg_url, data=payload, files=files, timeout=60)
                print("✅ Telegram Sent!")
        except Exception as e: print(f"❌ Telegram Error: {e}")

    if WEBHOOK_URL and catbox_url:
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
