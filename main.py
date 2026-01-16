import instaloader
import requests
import os
import json
from datetime import datetime

# --- CONFIGURATION (Secrets Environment se aayenge) ---
TARGET_USERNAME = "virtualaarvi"
DOWNLOAD_FOLDER = "downloads_temp"
HISTORY_FILE = "video_queue.json"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- FUNCTIONS ---
L = instaloader.Instaloader()

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"processed": []} # Structure simplified

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def send_to_telegram(file_path, caption):
    if not TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        with open(file_path, 'rb') as vf:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, files={'video': vf})
            print("✅ Sent to Telegram.")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def send_to_webhook(file_path, caption, link):
    if not WEBHOOK_URL: return
    try:
        with open(file_path, 'rb') as vf:
            requests.post(WEBHOOK_URL, files={'video': vf}, data={'caption': caption, 'url': link})
            print("✅ Sent to Webhook.")
    except: pass

# --- MAIN LOGIC (Run Once and Exit) ---
def run_job():
    print(f"[{datetime.now()}] Job Started...")
    
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

    data = load_history()
    processed_ids = set(data["processed"])

    # 1. Scan Profile
    try:
        print("Scanning profile...")
        profile = instaloader.Profile.from_username(L.context, TARGET_USERNAME)
        
        all_videos = []
        # Sirf pehle 50 posts scan karenge speed ke liye (Optimization)
        # Agar account naya hai to limit hata sakte hain
        count = 0
        for post in profile.get_posts():
            if post.is_video:
                all_videos.append({
                    "shortcode": post.shortcode,
                    "date": post.date_utc.timestamp(),
                    "caption": post.caption if post.caption else ""
                })
            count += 1
            if count > 100: break # Safety limit

        # 2. Sort: Oldest First
        all_videos.sort(key=lambda x: x["date"])

        # 3. Find Oldest Unsent Video
        target = None
        for vid in all_videos:
            if vid["shortcode"] not in processed_ids:
                target = vid
                break
        
        if target:
            print(f"🎯 Processing: {target['shortcode']}")
            post = instaloader.Post.from_shortcode(L.context, target['shortcode'])
            
            L.download_post(post, target=DOWNLOAD_FOLDER)
            
            # Find file
            video_path = None
            for root, _, files in os.walk(DOWNLOAD_FOLDER):
                for file in files:
                    if file.endswith(".mp4") and target['shortcode'] in file:
                        video_path = os.path.join(root, file)
            
            if video_path:
                link = f"https://www.instagram.com/p/{target['shortcode']}/"
                send_to_telegram(video_path, target['caption'])
                send_to_webhook(video_path, target['caption'], link)
                
                # Update History
                data["processed"].append(target['shortcode'])
                save_history(data)
                print("✅ History updated.")
            else:
                print("❌ Download failed.")
        else:
            print("⚠️ No new videos to post.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_job()
