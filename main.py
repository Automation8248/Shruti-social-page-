import instaloader
import requests
import os
import json
import time
from datetime import datetime

# --- CONFIGURATION ---
TARGET_USERNAME = "virtualaarvi"
DOWNLOAD_FOLDER = "downloads_temp"
HISTORY_FILE = "video_queue.json"

# Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
IG_USER = os.getenv("INSTAGRAM_USER") 
IG_PASS = os.getenv("INSTAGRAM_PASS") 

L = instaloader.Instaloader()

# --- HELPER FUNCTIONS ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {"processed": []}
    return {"processed": []}

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

# --- MAIN LOGIC ---
def run_job():
    print(f"[{datetime.now()}] Job Started...")

    # --- NEW ADDITION: FIX FOR .TXT FILE NAME ---
    # Ye code check karega ki agar file ka naam .txt hai to use sahi kar dega
    session_txt = f"session-{IG_USER}.txt"
    session_original = f"session-{IG_USER}"

    if os.path.exists(session_txt):
        print(f"🔄 Found .txt session file: {session_txt}")
        # Agar original naam se pehle koi kharab file hai to use hata do
        if os.path.exists(session_original):
            os.remove(session_original)
        # Rename karke sahi naam de do
        os.rename(session_txt, session_original)
        print(f"✅ File Renamed to: {session_original} (Ready for Login)")
    # --------------------------------------------
    
    # 1. SMART LOGIN (Session File First -> Then Password)
    session_file_path = f"session-{IG_USER}"
    
    try:
        if os.path.exists(session_file_path):
            print(f"Using Session File: {session_file_path}")
            L.load_session_from_file(IG_USER, filename=session_file_path)
            print("✅ Login via Session Successful!")
        elif IG_USER and IG_PASS:
            print(f"Session file not found. Trying Password Login for {IG_USER}...")
            L.login(IG_USER, IG_PASS)
            print("✅ Login via Password Successful!")
        else:
            print("⚠️ No Credentials found!")
    except Exception as e:
        print(f"❌ Login Error: {e}")
        print("Tip: Upload a session file to bypass 'Checkpoint' errors.")

    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

    data = load_history()
    processed_ids = set(data["processed"])

    try:
        print(f"Scanning profile: {TARGET_USERNAME} (Looking for oldest videos)...")
        profile = instaloader.Profile.from_username(L.context, TARGET_USERNAME)
        
        all_videos = []
        
        # NOTE: Hum loop chala rahe hain. Agar account bahut bada hai to time lega.
        # Hum pehle 100 posts scan karenge taaki process fast rahe.
        count = 0
        for post in profile.get_posts():
            if post.is_video:
                all_videos.append({
                    "shortcode": post.shortcode,
                    "date": post.date_utc.timestamp(), # Time for sorting
                    "caption": post.caption if post.caption else ""
                })
            count += 1
            if count >= 100: # Safety Limit (Change to higher number if needed)
                break 

        # --- IMPORTANT: SORT OLDEST FIRST ---
        # Low Timestamp = Old Date. High Timestamp = New Date.
        # Ye line videos ko Oldest -> Newest arrange kar degi.
        all_videos.sort(key=lambda x: x["date"])

        print(f"Found {len(all_videos)} videos. Checking for oldest unsent...")

        # Find the FIRST video in the list that is NOT in history
        target = None
        for vid in all_videos:
            if vid["shortcode"] not in processed_ids:
                target = vid
                break # Pehla milte hi ruk jao (Kyunki wo sorted list ka sabse purana hai)
        
        if target:
            print(f"🎯 Selected Oldest Available Video: {target['shortcode']}")
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
                print("✅ Task Completed.")
            else:
                print("❌ Download fail.")
        else:
            print("⚠️ All old videos are already sent!")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_job()
