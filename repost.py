import subprocess
import requests

PROFILE_URL = "https://www.instagram.com/virtualaarvi/"
TELEGRAM_BOT = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
WEBHOOK_URL = "YOUR_WEBHOOK"

# read index
with open("last_index.txt", "r") as f:
    index = int(f.read().strip())

# get reels list
cmd = [
    "yt-dlp",
    "--flat-playlist",
    "--dump-json",
    PROFILE_URL
]

result = subprocess.check_output(cmd).decode().splitlines()

videos = [line for line in result if '"url"' in line]
videos.reverse()  # OLDEST → NEWEST

if index >= len(videos):
    print("No new videos")
    exit()

video_data = videos[index]

# download video
subprocess.run([
    "yt-dlp",
    "-o", "video.mp4",
    PROFILE_URL
])

# upload to catbox
with open("video.mp4", "rb") as f:
    r = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"file": f}
    )

video_url = r.text

caption = "Repost from Instagram"

# send telegram
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
    data={
        "chat_id": CHAT_ID,
        "text": f"{caption}\n\n🎥 {video_url}"
    }
)

# webhook
requests.post(WEBHOOK_URL, json={
    "video": video_url,
    "caption": caption
})

# save progress
with open("last_index.txt", "w") as f:
    f.write(str(index + 1))
