import instaloader
import requests
from telegram import Bot
import os
import sys

# --- CONFIG ---
TARGET_USERNAME = "virtualaarvi"
BOT_USERNAME = os.getenv("BOT_USERNAME")
BOT_PASSWORD = os.getenv("BOT_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- CHECK SECRETS ---
if not BOT_USERNAME or not BOT_PASSWORD:
    print("❌ Error: BOT_USERNAME aur BOT_PASSWORD Secrets mein add karein!")
    sys.exit(1)

# Initialize Bot (Sync Version)
bot = Bot(token=TELEGRAM_TOKEN)

# --- LOGIN LOGIC ---
L = instaloader.Instaloader(download_videos=True, save_metadata=False, download_pictures=False)

try:
    print(f"Logging in as {BOT_USERNAME}...")
    L.login(BOT_USERNAME, BOT_PASSWORD)
    print("✅ Login Successful!")
except Exception as e:
    print(f"⚠️ Login Error (Checkpoint): {e}")
    print("👉 ACTION REQUIRED: Apne phone par Fake Account kholo aur 'This was me' click karo!")
    # Hum script rok nahi rahe, shayad bina login kaam ho jaye
    pass

# --- MAIN WORK ---
try:
    print(f"Fetching posts for: {TARGET_USERNAME}")
    profile = instaloader.Profile.from_username(L.context, TARGET_USERNAME)
    
    # Last Video Load (Safe Mode)
    if not os.path.exists("last_video.txt"):
        with open("last_video.txt", "w") as f: f.write("")
    
    with open("last_video.txt", "r") as f:
        last_video = f.read().strip()

    count = 0
    for post in profile.get_posts():
        count += 1
        if count > 5: break # Sirf top 5 check karo

        if post.shortcode == last_video:
            print("⏳ No new videos.")
            break
        
        if post.is_video:
            print(f"🚀 New Video Found: {post.shortcode}")
            
            caption_text = post.caption if post.caption else ""
            final_caption = f"{caption_text}\n\n🎥 Credit: @{TARGET_USERNAME}"

            try:
                # 1. Telegram Send
                bot.send_video(chat_id=TELEGRAM_CHAT_ID, video=post.video_url, caption=final_caption)
                print("✅ Telegram Sent")

                # 2. Webhook Send (Only if URL exists)
                if WEBHOOK_URL and WEBHOOK_URL.startswith("http"):
                    try:
                        requests.post(WEBHOOK_URL, json={
                            "username": TARGET_USERNAME,
                            "video": post.shortcode,
                            "caption": caption_text
                        })
                        print("✅ Webhook Sent")
                    except Exception as e:
                        print(f"❌ Webhook Error: {e}")
                
                # 3. Save ID
                with open("last_video.txt", "w") as f:
                    f.write(post.shortcode)
                
                break # Ek baar mein 1 video

            except Exception as e:
                print(f"❌ Sending Failed: {e}")

except Exception as e:
    print(f"Script Error: {e}")
