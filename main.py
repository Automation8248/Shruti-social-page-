import instaloader
import os
import requests
import json

USERNAME = "virtualaarvi"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

L = instaloader.Instaloader(
    download_videos=True,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_json=False
)

# Login using session
L.load_session_from_file(os.getenv("IG_USERNAME"), "session")

profile = instaloader.Profile.from_username(L.context, USERNAME)

posts = list(profile.get_posts())
posts.reverse()  # oldest → newest

# Track last posted
STATE_FILE = "state.json"
last_index = 0

if os.path.exists(STATE_FILE):
    last_index = json.load(open(STATE_FILE))["index"]

post = posts[last_index]

L.download_post(post, target="video")

video_file = None
for f in os.listdir("video"):
    if f.endswith(".mp4"):
        video_file = f
        break

# Upload to catbox.moe
with open(f"video/{video_file}", "rb") as f:
    r = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": f},
    )

video_url = r.text.strip()
caption = post.caption or "No caption"

message = f"{caption}\n\n🎬 {video_url}"

# Send Telegram
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": message}
)

# Send Webhook
requests.post(
    WEBHOOK_URL,
    json={"text": message}
)

# Save progress
json.dump({"index": last_index + 1}, open(STATE_FILE, "w"))
