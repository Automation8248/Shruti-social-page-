import os
import requests
import yt_dlp
import sys
import glob
import re
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
VIDEO_LIST_FILE = 'videos.txt'
HISTORY_FILE = 'history.txt'
# Environment variables se data le rahe hain (Make sure ye set ho)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

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
    
    # Koshish karein translate karne ki
    try:
        translated = GoogleTranslator(source='auto', target='hi').translate(text)
        if is_text_safe(translated):
            words = translated.split()
            return " ".join(words[:4])
    except Exception as e:
        print(f"⚠️ Translation Failed: {e}")
    
    # Agar translation fail ho, to original text use karein (Fallback)
    if is_text_safe(text):
        words = text.split()
        return " ".join(words[:4])
    
    return None

def get_smart_caption_text(vtt_file_path, description, title):
    # 1. AUDIO CHECK (Subtitles)
    if vtt_file_path and os.path.exists(vtt_file_path):
        try:
            with open(vtt_file_path, 'r', encoding='utf-8') as f: content = f.read()
            lines = content.splitlines()
            spoken_text = []
            for line in lines:
                # VTT formatting clean karna
                if '-->' in line or line.strip() == '' or line.startswith('WEBVTT') or line.isdigit(): continue
                clean = re.sub(r'<[^>]+>', '', line).strip()
                clean = re.sub(r'\[.*?\]', '', clean)
                if clean and clean not in spoken_text: spoken_text.append(clean)
            
            full_speech = " ".join(spoken_text[:3])
            hindi_audio = translate_and_shorten(full_speech)
            if hindi_audio: return hindi_audio
        except Exception as e: print(f"⚠️ VTT Error: {e}")

    # 2. DESCRIPTION CHECK
    if description:
        clean_desc = description.split('\n')[0]
        clean_desc = re.sub(r'#\w+', '', clean_desc).strip()
        hindi_desc = translate_and_shorten(clean_desc)
        if hindi_desc: return hindi_desc

    # 3. TITLE CHECK
    if title:
        clean_title = re.sub(r'#\w+', '', title).strip()
        hindi_title = translate_and_shorten(clean_title)
        if hindi_title: return hindi_title

    return "देखिए आज का वीडियो"

def generate_hashtags(original_tags):
    final_tags = ["#aarvi"]
    forbidden = ["virtualaarvi", "aarvi"]
    
    if original_tags:
        for tag in original_tags:
            clean_tag = tag.replace(" ", "").lower()
            if clean_tag not in forbidden and f"#{clean_tag}" not in final_tags:
                final_tags.append(f"#{clean_tag}")
    
    # Tags kam hain to SEO tags add karein
    for seo in SEO_TAGS:
        if len(final_tags) < 6:
            if seo not in final_tags: final_tags.append(seo)
        else: break
    return " ".join(final_tags[:6])

def download_video_data(url):
    print(f"⬇️ Downloading: {url}")
    
    # Purane temp files delete karein
    for f in glob.glob("temp_video*"):
        try: os.remove(f)
        except: pass

    # --- SUDHAR 1: Anti-Block Headers ---
    ydl_opts = {
        'format': 'best', # Best available quality
        'outtmpl': 'temp_video.%(ext)s',
        'quiet': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'hi', 'auto'],
        
        # Security Bypass Settings
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'geo_bypass': True,
        # Fake User Agent (Mobile Browser jaisa dikhne ke liye)
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.instagram.com/',
    }
    
    dl_filename = None
    final_hindi_text = ""

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info: return None

            title = info.get('title', '')
            desc = info.get('description', '')
            hashtags = generate_hashtags(info.get('tags', []))
            
            # --- SUDHAR 2: Sahi file dhundna ---
            # yt-dlp kabhi .mp4 kabhi .mkv karta hai, isliye glob use kiya
            found_files = glob.glob("temp_video*")
            # Filter to keep only video/audio files (exclude subtitles)
            video_files = [f for f in found_files if not f.endswith('.vtt')]
            
            if video_files:
                dl_filename = video_files[0]
            else:
                print("❌ File downloaded but not found on disk.")
                return None

            # Subtitle check
            vtt_file = None
            sub_files = glob.glob("temp_video*.vtt")
            if sub_files: vtt_file = sub_files[0]
            
            final_hindi_text = get_smart_caption_text(vtt_file, desc, title)

    except Exception as e:
        print(f"❌ Download Error: {e}")
        return None

    return {
        "filename": dl_filename,
        "title": title,
        "hindi_text": final_hindi_text,
        "hashtags": hashtags,
        "original_url": url
    }

def upload_to_catbox(filepath):
    print("🚀 Uploading to Catbox...")
    try:
        with open(filepath, "rb") as f:
            # Timeout add kiya taaki hang na ho
            response = requests.post(
                "https://catbox.moe/user/api.php", 
                data={"reqtype": "fileupload"}, 
                files={"fileToUpload": f},
                timeout=60
            )
            if response.status_code == 200:
                link = response.text.strip()
                print(f"✅ Uploaded: {link}")
                return link
            else:
                print(f"⚠️ Catbox Upload Failed: {response.status_code}")
                return None
    except Exception as e:
        print(f"⚠️ Catbox Error: {e}")
        return None

def send_notifications(video_data, catbox_url):
    print("\n--- Sending Notifications ---")
    tg_caption = f"{video_data['hindi_text']}\n.\n.\n.\n.\n.\n{video_data['hashtags']}"
    
    # 1. TELEGRAM (Video File)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("📤 Telegram Video Sending...")
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        try:
            with open(video_data['filename'], 'rb') as video_file:
                payload = {
                    "chat_id": str(TELEGRAM_CHAT_ID), 
                    "caption": tg_caption, 
                    "parse_mode": "Markdown"
                }
                files = {'video': video_file}
                requests.post(tg_url, data=payload, files=files, timeout=60)
                print("✅ Telegram Sent!")
        except Exception as e: print(f"❌ Telegram Error: {e}")

    # 2. WEBHOOK (Catbox URL Only)
    if WEBHOOK_URL:
        if catbox_url and "catbox.moe" in catbox_url:
            print(f"📤 Webhook Sending...")
            payload = {
                "content": tg_caption, 
                "video_url": catbox_url,
                "title_original": video_data['title']
            }
            try: 
                requests.post(WEBHOOK_URL, json=payload, timeout=30)
                print("✅ Webhook Sent!")
            except Exception as e: print(f"❌ Webhook Error: {e}")
        else:
            print("⚠️ Webhook skipped: Catbox link missing.")

def update_history(url):
    with open(HISTORY_FILE, 'a') as f: f.write(url + '\n')

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    next_url = get_next_video()
    if not next_url:
        print("💤 No new videos found in videos.txt")
        sys.exit(0)
    
    data = download_video_data(next_url)
    
    if data and data['filename']:
        # Catbox upload zaroori hai Webhook ke liye
        catbox_link = upload_to_catbox(data['filename'])
        
        send_notifications(data, catbox_link)
        update_history(next_url)
        
        # Cleanup
        if os.path.exists(data['filename']): os.remove(data['filename'])
        # Subtitles cleanup
        for f in glob.glob("temp_video*.vtt"):
            os.remove(f)
            
        print("✅ Task Completed Successfully.")
    else:
        print("❌ Task Failed: Video download or processing error.")
        sys.exit(1)
