import instaloader
import requests
import os
from telegram import Bot

# ================= CONFIG =================
INSTAGRAM_USERNAME = "virtualaarvi"

# 👉 Apna Telegram USER CHAT ID yahan daalo (number, quotes nahi)
TELEGRAM_CHAT_ID = 123456789  

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

LAST_FILE = "last_video.txt"
VIDEO_FILE = "video.mp4"
# =========================================

# Telegram Bot
bot = Bot(token=TELEGRAM_TOKEN)

# Instaloader
L = instaloader.Instaloader(download_videos=False, save_metadata=False)

profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USERNAME)

# Last posted video load
last_shortcode = ""
if os.path.exists(LAST_FILE):
    last_shortcode = open(LAST_FILE, "r").read().strip()

for post in profile.get_posts():

    if not post.is_video:
        continue

    # Agar ye video pehle bheja ja chuka hai → stop
    if post.shortcode == last_shortcode:
        break

    # 🔗 Instagram video link (Copy link)
    video_link = f"https://www.instagram.com/reel/{post.shortcode}/"

    # 🎥 Direct mp4 URL
    video_url = post.video_url

    # 📝 Caption + hashtags
    caption_text = post.caption if post.caption else ""

    final_caption = (
        f"{caption_text}\n\n"
        f"🔗 {video_link}\n"
        f"🎥 Credit: @{INSTAGRAM_USERNAME}"
    )

    # ⬇️ Video download (through link)
    video_data = requests.get(video_url).content
    with open(VIDEO_FILE, "wb") as f:
        f.write(video_data)

    # 📤 Send video to YOU (user)
    bot.send_video(
        chat_id=TELEGRAM_CHAT_ID,
        video=open(VIDEO_FILE, "rb"),
        caption=final_caption[:1024]  # Telegram limit
    )

    # 🌐 Webhook notify
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={
            "username": INSTAGRAM_USERNAME,
            "video_link": video_link,
            "caption": caption_text,
            "status": "sent_to_user"
        })

    # 💾 Save last sent video
    with open(LAST_FILE, "w") as f:
        f.write(post.shortcode)

    break  # Daily sirf 1 video
