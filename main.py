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

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Filler tags (Total 5 hashtags maintain karne ke liye)
SEO_TAGS = ["#reels", "#trending", "#viral", "#explore", "#love", "#shayari"]

def get_next_video():
    processed_urls = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            processed_urls = [line.strip() for line in f.readlines()]

    if not os.path.exists(VIDEO_LIST_FILE):
        print("❌ Error: videos.txt file nahi mili!")
        return None

    with open(VIDEO_LIST_FILE, 'r') as f:
        all_urls = [line.strip() for line in f.readlines() if line.strip()]

    for url in all_urls:
        if url not in processed_urls:
            return url
    return None

# --- NEW LOGIC: Extract Audio Text -> Translate -> Take 4 Words ---
def get_audio_text_hindi(vtt_file_path, fallback_title):
    try:
        # 1. Read Subtitle File
        with open(vtt_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 2. Clean VTT junk (timestamps, tags, header)
        lines = content.splitlines()
        spoken_text = []
        for line in lines:
            if '-->' in line or line.strip() == '' or line.startswith('WEBVTT') or line.strip().isdigit():
                continue
            # Remove HTML-like tags <c> etc
            clean = re.sub(r'<[^>]+>', '', line).strip()
            # Remove timestamps inside text if any
            clean = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}', '', clean)
            if clean and clean not in spoken_text:
                spoken_text.append(clean)
        
        # Join first few lines to get context
        full_spoken_text = " ".join(spoken_text[:3]) 
        
        if not full_spoken_text:
            print("⚠️ No spoken text found, using Title as fallback.")
            full_spoken_text = fallback_title

        print(f"🗣️ Original Spoken: {full_spoken_text}")

        # 3. Translate to Hindi
        translated = GoogleTranslator(source='auto', target='hi').translate(full_spoken_text)
        print(f"🇮🇳 Hindi Translated: {translated}")
        
        # 4. Take First 4 Words
        words = translated.split()
        final_4_words = " ".join(words[:4])
        
        return final_4_words

    except Exception as e:
        print(f"❌ Audio Text Error: {e}")
        # Fallback to Title if subtitle parsing fails
        try:
            fallback = GoogleTranslator(source='auto', target='hi').translate(fallback_title)
            return " ".join(fallback.split()[:4])
        except:
            return "New Video Update"

def generate_hashtags(original_tags):
    final_tags = []
    
    # 1. First Tag is ALWAYS #aarvi
    final_tags.append("#aarvi")
    
    # 2. Add video's original tags (excluding forbidden ones)
    forbidden = ["virtualaarvi", "aarvi"]
    
    for tag in original_tags:
        clean_tag = tag.replace(" ", "").lower()
        if clean_tag not in forbidden and f"#{clean_tag}" not in final_tags:
            final_tags.append(f"#{clean_tag}")
            
    # 3. Fill up to exactly 5 tags
    for seo in SEO_TAGS:
        if len(final_tags) < 5:
            if seo not in final_tags:
                final_tags.append(seo)
        else:
            break
            
    return " ".join(final_tags[:5])

def download_video_data(url):
    print(f"⬇️ Downloading: {url}")
    for f in glob.glob("temp_video*"):
        try: os.remove(f)
        except: pass

    # Settings to force download subtitles (Auto-generated)
    ydl_opts = {
        'format': 'best[ext=mp4]',
        'outtmpl': 'temp_video.%(ext)s',
        'quiet': True,
        'writesubtitles': True,
        'writeautomaticsub': True, # Important: Gets auto-generated speech-to-text
        'subtitleslangs': ['en', 'hi', 'auto'], # Get English/Hindi/Auto
    }
    
    dl_filename = None
    hindi_content_text = ""

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            dl_filename = ydl.prepare_filename(info)
            title = info.get('title', 'No Title')
            
            # --- HASHTAGS ---
            tags_list = info.get('tags', [])
            hashtags = generate_hashtags(tags_list)

            # --- PROCESS CAPTIONS FOR CONTENT ---
            # Find the .vtt file
            sub_files = glob.glob("temp_video*.vtt")
            if sub_files:
                print(f"✅ Subtitles found (Audio content available).")
                hindi_content_text = get_audio_text_hindi(sub_files[0], title)
            else:
                print("⚠️ No subtitles found. Using Title Translation.")
                trans_title = GoogleTranslator(source='auto', target='hi').translate(title)
                hindi_content_text = " ".join(trans_title.split()[:4])

    except Exception as e:
        print(f"❌ Download Error: {e}")
        return None

    return {
        "filename": dl_filename,
        "title": title,
        "hindi_text": hindi_content_text, # This is now from Audio/Speech
        "hashtags": hashtags,
        "original_url": url
    }

def upload_to_catbox(filepath):
    print("🚀 Uploading to Catbox...")
    try:
        with open(filepath, "rb") as f:
            response = requests.post(
                "https://catbox.moe/user/api.php", 
                data={"reqtype": "fileupload"}, 
                files={"fileToUpload": f}
            )
            if response.status_code == 200:
                return response.text.strip()
            else:
                return None
    except:
        return None

def send_notifications(video_data, catbox_url):
    print("\n--- Sending Notifications ---")
    
    # --- Caption Format ---
    # 1. Hindi words from SPEECH
    # 2. 5 Dots
    # 3. 5 Hashtags
    tg_caption = f"{video_data['hindi_text']}\n.\n.\n.\n.\n.\n{video_data['hashtags']}"
    
    # --- 1. TELEGRAM ---
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("📤 Sending Video...")
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        
        try:
            with open(video_data['filename'], 'rb') as video_file:
                payload = {
                    "chat_id": str(TELEGRAM_CHAT_ID),
                    "caption": tg_caption,
                    "parse_mode": "Markdown"
                }
                files = {'video': video_file}
                resp = requests.post(tg_url, data=payload, files=files)
                if resp.status_code == 200: print("✅ Telegram Success!")
                else: print(f"❌ Telegram Fail: {resp.text}")
        except Exception as e:
            print(f"❌ Telegram Error: {e}")

    # --- 2. WEBHOOK ---
    if WEBHOOK_URL:
        print(f"Sending to Webhook...")
        webhook_payload = {
            "content": tg_caption,
            "video_url": catbox_url,
            "title_original": video_data['title'],
            "hashtags": video_data['hashtags']
        }
        try:
            requests.post(WEBHOOK_URL, json=webhook_payload)
            print("✅ Webhook Sent!")
        except: pass

def update_history(url):
    with open(HISTORY_FILE, 'a') as f:
        f.write(url + '\n')

if __name__ == "__main__":
    next_url = get_next_video()
    if not next_url:
        print("💤 No new videos.")
        sys.exit(0)
    
    data = download_video_data(next_url)
    if data and data['filename']:
        catbox_link = upload_to_catbox(data['filename'])
        if not catbox_link: catbox_link = "Upload Failed"
        
        send_notifications(data, catbox_link)
        update_history(next_url)
        
        if os.path.exists(data['filename']): os.remove(data['filename'])
        print("✅ Task Done.")
    else:
        sys.exit(1)
