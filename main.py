import subprocess
import os
import requests

PROFILE_URL = "https://www.instagram.com/virtualaarvi/"
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
WEBHOOK_URL = "YOUR_WEBHOOK_URL"

USED_FILE = "used.txt"

if not os.path.exists(USED_FILE):
    open(USED_FILE, "w").close()

with open(USED_FILE, "r") as f:
    used = f.read().splitlines()

# Get all video URLs (oldest first)
result = subprocess.check_output([
    "yt-dlp",
    "--flat-playlist",
    "--playlist-reverse",
    "-J",
    PROFILE_URL
]).decode()

import json
data = json.loads(result)

next_video = None
for entry in data["entries"]:
    url = entry["url"]
    if url not in used:
        next_video = url
        break

if not next_video:
    print("No new video found")
    exit()

# Download video + caption
subprocess.run([
    "yt-dlp",
    next_video,
    "-o", "video.%(ext)s",
    "--merge-output-format", "mp4",
    "--write-description"
])

# Read caption
caption = ""
if os.path.exists("video.description"):
    with open("video.description", "r", encoding="utf-8") as f:
        caption = f.read()

# Send to Telegram
with open("video.mp4", "rb") as v:
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
        data={"chat_id": CHAT_ID, "caption": caption[:1024]},
        files={"video": v}
    )

# Send to Webhook
requests.post(WEBHOOK_URL, json={
    "video": next_video,
    "caption": caption
})

# Mark as used
with open(USED_FILE, "a") as f:
    f.write(next_video + "\n")
