import os
import requests
import yt_dlp
import sys
import json
import subprocess
import glob
import re

# --- CONFIGURATION ---
VIDEO_LIST_FILE = 'videos.txt'
HISTORY_FILE = 'history.txt'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
TEMP_DL_NAME = "temp_video"
PROCESSED_NAME = "final_video.mp4"
NEW_WATERMARK_TEXT = "Shruti"

def get_next_video():
    processed_urls = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            processed_urls = [line.strip() for line in f.readlines()]

    if not os.path.exists(VIDEO_LIST_FILE):
        print("Error: videos.txt not found!")
        return None

    with open(VIDEO_LIST_FILE, 'r') as f:
        all_urls = [line.strip() for line in f.readlines() if line.strip()]

    for url in all_urls:
        if url not in processed_urls:
            return url
    return None

# Function to clean subtitle text (remove timestamps)
def clean_vtt_text(vtt_content):
    # Remove header
    lines = vtt_content.splitlines()
    clean_lines = []
    for line in lines:
        # Skip timestamps, headers, empty lines
        if '-->' in line or line.strip() == '' or line.startswith('WEBVTT') or line.strip().isdigit():
            continue
        # Remove tags like <c> or <b>
        clean_line = re.sub(r'<[^>]+>', '', line).strip()
        if clean_line and clean_line not in clean_lines: # Avoid immediate duplicates
            clean_lines.append(clean_line)
    return "\n".join(clean_lines[:50]) # Limit to first 50 lines so post isn't too long

def download_video_data(url):
    print(f"Processing: {url}")
    # Remove previous temp files
    for f in glob.glob(f"{TEMP_DL_NAME}*"):
        os.remove(f)

    ydl_opts = {
        'format': 'best[ext=mp4]', # Prefer MP4 for easier ffmpeg processing
        'outtmpl': f'{TEMP_DL_NAME}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # Caption settings
        'writesubtitles': True,
        'writeautomaticsub': True, # Fallback to auto-captions if no manual ones
        'subtitleslangs': ['en', 'hi', 'auto'], # Prefer English or Hindi
        'skip_download': False,
    }
    
    caption_text = "No captions available."
    dl_filename = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        dl_filename = ydl.prepare_filename(info)
        
        title = info.get('title', 'No Title')
        description = info.get('description', '')
        tags = info.get('tags', [])
        hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in tags[:10]])

        # Find downloaded subtitle file (.vtt)
        sub_files = glob.glob(f"{TEMP_DL_NAME}*.vtt")
        if sub_files:
            print(f"Found subtitle file: {sub_files[0]}")
            try:
                with open(sub_files[0], 'r', encoding='utf-8') as f:
                    raw_sub = f.read()
                    caption_text = clean_vtt_text(raw_sub)
                os.remove(sub_files[0]) # Clean up subtitle file
            except Exception as e:
                print(f"Error reading subtitles: {e}")

    return {
        "filename": dl_filename,
        "title": title,
        "hashtags": hashtags,
        "description": description,
        "captions": caption_text
    }

# Function to add "Shruti" and cover old watermark using ffmpeg
def process_watermark(input_file, output_file, text):
    print(f"Adding watermark '{text}'...")
    # FFmpeg command breakdown:
    # drawtext: Adds text
    # text='...': The text to add
    # fontcolor=white: Text color
    # fontsize=24: Size
    # x=(w-text_w)/2: Center horizontally
    # y=h-th-30: Position near bottom (30 pixels from bottom)
    # box=1: Add a background box behind text
    # boxcolor=black@0.7: Semi-transparent black box to cover old text
    # boxborderw=5: Padding around the box
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', f"drawtext=text='{text}':fontcolor=white:fontsize=26:x=(w-text_w)/2:y=h-th-40:box=1:boxcolor=black@0.6:boxborderw=10",
        '-c:a', 'copy', # Copy audio without re-encoding (faster)
        '-y', # Overwrite output if exists
        output_file
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Watermark processed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error: {e.stderr.decode()}")
        return False

def upload_to_catbox(filepath):
    print("Uploading to Catbox.moe...")
    url = "https://catbox.moe/user/api.php"
    try:
        with open(filepath, "rb") as f:
            data = {"reqtype": "fileupload"}
            files = {"fileToUpload": f}
            response = requests.post(url, data=data, files=files)
            if response.status_code == 200:
                return response.text.strip()
            else:
                print(f"Catbox Error: {response.text}")
                return None
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

def send_notifications(video_data, catbox_url):
    # Constructing the message with captions
    caption = f"🎬 **{video_data['title']}**\n\n"
    caption += f"{video_data['hashtags']}\n\n"
    
    if video_data['captions'] and video_data['captions'] != "No captions available.":
         caption += f"📝 **Captions/Quotes:**\n_{video_data['captions']}_\n\n"

    caption += f"🔗 Watch/Download: {catbox_url}"
    
    # 1. Send to Telegram Bot
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            # Using string format for user ID to be safe
            "chat_id": str(TELEGRAM_CHAT_ID), 
            "text": caption,
            "parse_mode": "Markdown"
        }
        # Split message if too long for Telegram (limit is ~4096 chars)
        if len(caption) > 4000:
             payload["text"] = caption[:4000] + "...(truncated)"
             
        requests.post(tg_url, json=payload)
        print("Sent to Telegram.")

    # 2. Send to Webhook
    if WEBHOOK_URL:
        webhook_payload = {
            "title": video_data['title'],
            "video_url": catbox_url,
            "hashtags": video_data['hashtags'],
            "captions": video_data['captions'],
            "original_desc": video_data['description']
        }
        try:
            requests.post(WEBHOOK_URL, json=webhook_payload)
            print("Sent to Webhook.")
        except Exception as e:
            print(f"Webhook Error: {e}")

def update_history(url):
    with open(HISTORY_FILE, 'a') as f:
        f.write(url + '\n')

# --- MAIN EXECUTION FLOW ---
if __name__ == "__main__":
    next_url = get_next_video()
    
    if not next_url:
        print("No new videos to process today!")
        sys.exit(0)
        
    downloaded_file = None
    try:
        # 1. Download Video & Captions
        data = download_video_data(next_url)
        downloaded_file = data['filename']
        
        if not downloaded_file or not os.path.exists(downloaded_file):
             print("Download failed.")
             sys.exit(1)

        # 2. Process Video (Remove old watermark, add "Shruti")
        processing_success = process_watermark(downloaded_file, PROCESSED_NAME, NEW_WATERMARK_TEXT)
        
        if not processing_success:
            print("Video processing failed.")
            sys.exit(1)
            
        # 3. Upload processed video to Catbox
        catbox_link = upload_to_catbox(PROCESSED_NAME)
        
        if catbox_link:
            print(f"Catbox URL: {catbox_link}")
            
            # 4. Send Alerts (with captions)
            send_notifications(data, catbox_link)
            
            # 5. Update History
            update_history(next_url)
            
            print("Task Completed Successfully.")
        else:
            print("Failed to upload to Catbox.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Critical Error: {e}")
        # Clean up files on error
        if downloaded_file and os.path.exists(downloaded_file): os.remove(downloaded_file)
        if os.path.exists(PROCESSED_NAME): os.remove(PROCESSED_NAME)
        sys.exit(1)
    finally:
        # Final Cleanup
        if downloaded_file and os.path.exists(downloaded_file): os.remove(downloaded_file)
        if os.path.exists(PROCESSED_NAME): os.remove(PROCESSED_NAME)
        # Remove any stray subtitle files
        for f in glob.glob(f"{TEMP_DL_NAME}*"): os.remove(f)
