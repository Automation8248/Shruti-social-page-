import os
import subprocess
import requests
import sys

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Load all links
with open("links.txt", "r") as f:
    all_links = [l.strip() for l in f if l.strip()]

# Load used links
if not os.path.exists("used.txt"):
    open("used.txt", "w").close()

with open("used.txt", "r") as f:
    used_links = set(l.strip() for l in f if l.strip())

# Pick next unused link (NO REPEAT)
next_link = None
for link in all_links:
    if link not in used_links:
        next_link = link
        break

if not next_link:
    print("✅ All videos already posted. No repeat.")
    sys.exit(0)

# Download video + caption
subprocess.run([
    "yt-dlp",
    next_link,
    "-o", "video.%(ext)s",
    "--merge-output-format", "mp4",
    "--write-description"
], check=True)

# Read caption + hashtags
caption = ""
if os.path.exists("video.description"):
    with open("video.description", "r", encoding="utf-8") as f:
        caption = f.read().strip()

# Send to Telegram
with open("video.mp4", "rb") as video:
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
        data={
            "chat_id": CHAT_ID,
            "caption": caption[:1024]
        },
        files={"video": video},
        timeout=30
    )

# Send to Webhook
requests.post(
    WEBHOOK_URL,
    json={
        "source": next_link,
        "caption": caption
    },
    timeout=30
)

# Mark link as used (PREVENT REPEAT)
with open("used.txt", "a") as f:
    f.write(next_link + "\n")

print("✅ Video posted successfully")
