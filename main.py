import instaloader
import requests
from telegram import Bot
import os
import sys

# --- CONFIG (GitHub Secrets se values uthayega) ---
# Direct values na dalein, security ke liye
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not INSTAGRAM_USERNAME or not TELEGRAM_TOKEN:
    print("Error: Secrets set nahi hain!")
    sys.exit(1)

bot = Bot(token=TELEGRAM_TOKEN)
L = instaloader.Instaloader(download_videos=True, save_metadata=False, download_pictures=False)

# Optional: Agar login session use karna ho to
# L.load_session_from_file(INSTAGRAM_USERNAME) 

try:
    profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USERNAME)
except Exception as e:
    print(f"Profile Error: {e}")
    sys.exit(1)

# Load last video
try:
    with open("last_video.txt", "r") as f:
        last_video = f.read().strip()
except FileNotFoundError:
    last_video = ""

for post in profile.get_posts():
    if post.shortcode == last_video:
        print("No new posts.")
        break
    
    if post.is_video:
        video_url = post.video_url
        original_caption = post.caption if post.caption else ""
        final_caption = f"{original_caption}\n\n🎥 Credit: @{INSTAGRAM_USERNAME}"

        try:
            # Telegram
            bot.send_video(chat_id=TELEGRAM_CHAT_ID, video=video_url, caption=final_caption)
            
            # Webhook
            requests.post(WEBHOOK_URL, json={
                "username": INSTAGRAM_USERNAME,
                "video": post.shortcode,
                "caption": original_caption,
                "status": "posted"
            })
            
            print(f"Posted: {post.shortcode}")

            # Save aur Break (Ek baar mein ek hi video post karega safe rehne ke liye)
            with open("last_video.txt", "w") as f:
                f.write(post.shortcode)
            break 
            
        except Exception as e:
            print(f"Error: {e}")
