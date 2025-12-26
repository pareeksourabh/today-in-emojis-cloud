#!/usr/bin/env python3
"""
Post the daily emoji image to Instagram.

Uses the Instagram Graph API to publish images.
Requires the image to be publicly accessible via URL.

Environment variables:
- INSTAGRAM_ACCESS_TOKEN: Page access token with instagram_content_publish permission
- INSTAGRAM_BUSINESS_ACCOUNT_ID: Instagram business account ID
"""

import os
import sys
import json
import time
import requests
from datetime import date

# Configuration
INPUT_FILE = "public/data/today.json"
IMAGE_DIR = "public/images/daily"
POSTED_LOG = "data/instagram_posted.json"
GRAPH_API_VERSION = "v18.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# For GitHub Pages hosting
GITHUB_PAGES_BASE = "https://todayinemojis.com"

def get_env_vars():
    """Get required environment variables."""
    access_token = os.environ.get('INSTAGRAM_ACCESS_TOKEN')
    account_id = os.environ.get('INSTAGRAM_BUSINESS_ACCOUNT_ID')

    if not access_token:
        print("[error] INSTAGRAM_ACCESS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if not account_id:
        print("[error] INSTAGRAM_BUSINESS_ACCOUNT_ID not set", file=sys.stderr)
        sys.exit(1)

    return access_token, account_id

def was_already_posted(timestamp):
    """Check if this timestamp was already posted to Instagram."""
    if not os.path.exists(POSTED_LOG):
        return False

    try:
        with open(POSTED_LOG, 'r', encoding='utf-8') as f:
            posted = json.load(f)
            return timestamp in posted.get('timestamps', [])
    except Exception as e:
        print(f"[warn] Could not read posted log: {e}", file=sys.stderr)
        return False

def mark_as_posted(timestamp, media_id):
    """Record that this timestamp was posted to Instagram."""
    posted = {'timestamps': [], 'posts': []}

    if os.path.exists(POSTED_LOG):
        try:
            with open(POSTED_LOG, 'r', encoding='utf-8') as f:
                posted = json.load(f)
        except Exception:
            pass

    if 'timestamps' not in posted:
        posted['timestamps'] = []
    if 'posts' not in posted:
        posted['posts'] = []

    posted['timestamps'].append(timestamp)
    posted['posts'].append({
        'timestamp': timestamp,
        'media_id': media_id,
        'posted_at': date.today().isoformat()
    })

    # Keep only last 100 posts (about 2 weeks at 6/day)
    posted['timestamps'] = posted['timestamps'][-100:]
    posted['posts'] = posted['posts'][-100:]

    os.makedirs(os.path.dirname(POSTED_LOG), exist_ok=True)
    with open(POSTED_LOG, 'w', encoding='utf-8') as f:
        json.dump(posted, f, indent=2)

    print(f"[info] Marked {timestamp} as posted")

def load_emoji_data():
    """Load today's emoji data for caption generation."""
    if not os.path.exists(INPUT_FILE):
        print(f"[error] Input file not found: {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_image_url(data):
    """Get the public URL for today's image."""
    timestamp = data.get('timestamp', '')

    if timestamp:
        # Convert timestamp to filename-safe format: 2025-11-22T08:00:00Z -> 2025-11-22-0800
        filename_base = timestamp.replace(':', '').replace('T', '-').replace('Z', '')[:15]
    else:
        filename_base = data.get('date', date.today().isoformat())

    # The image will be hosted on GitHub Pages after commit
    image_url = f"{GITHUB_PAGES_BASE}/images/daily/{filename_base}.png"

    return image_url

def verify_image_accessible(image_url, max_attempts=10):
    """Verify the image URL is publicly accessible."""
    for attempt in range(max_attempts):
        try:
            response = requests.head(image_url, timeout=10)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    print(f"[success] Image verified accessible: {response.status_code}")
                    return True
                else:
                    print(f"[warn] Unexpected content-type: {content_type}")
            else:
                print(f"[info] Image not ready (status {response.status_code}), attempt {attempt + 1}/{max_attempts}")
        except Exception as e:
            print(f"[warn] Image check failed: {e}, attempt {attempt + 1}/{max_attempts}")

        time.sleep(10)

    print(f"[error] Image not accessible after {max_attempts} attempts", file=sys.stderr)
    return False

def generate_essence_caption(data):
    """Generate Instagram caption for essence posts."""
    essence = data.get('essence', {}) if isinstance(data.get('essence'), dict) else {}
    emotion_label = (essence.get('emotion_label') or "neutral").strip()
    emoji = (essence.get('emoji') or "🌍").strip()
    rationale = (essence.get('rationale') or "a mix of signals").strip()

    caption_parts = [
        f"Today I am {emotion_label} because {rationale}.",
        "",
        f"{emoji}",
        "",
        "#TodayInEmojis #EssenceOfTheDay #DailyMood",
        "",
        "todayinemojis.com",
    ]

    return '\n'.join(caption_parts)


def generate_caption(data):
    """Generate Instagram caption from emoji data."""
    if data.get('post_type') == 'essence':
        return generate_essence_caption(data)

    emojis = data.get('emojis', [])

    # Get emoji characters and labels
    emoji_chars = ' '.join([e.get('char', '') for e in emojis])
    labels = [e.get('label', '') for e in emojis]

    # Build caption
    caption_parts = [
        f"Today's vibe {emoji_chars}",
        "",
        "Feel the day. Don't read it.",
        "",
    ]

    # Add labels prefixed by emoji
    for emoji, label in zip([e.get('char', '') for e in emojis], labels):
        if label:
            prefix = emoji if emoji else "•"
            label_text = label.strip()
            if label_text:
                label_text = label_text[0].upper() + label_text[1:]
            caption_parts.append(f"{prefix} {label_text}")

    caption_parts.extend([
        "",
        "#TodayInEmojis #DailyVibes #NewsInEmojis #Minimalism #FiveEmojis #WorldNews #DailyMood",
        "",
        "todayinemojis.com"
    ])

    return '\n'.join(caption_parts)

def create_media_container(account_id, access_token, image_url, caption):
    """Create a media container for the image."""
    url = f"{GRAPH_API_BASE}/{account_id}/media"

    params = {
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token
    }

    print(f"[info] Creating media container...")
    print(f"[info] Image URL: {image_url}")

    response = requests.post(url, params=params)

    if response.status_code != 200:
        print(f"[error] Failed to create media container: {response.status_code}", file=sys.stderr)
        print(f"[error] Response: {response.text}", file=sys.stderr)
        return None

    data = response.json()
    container_id = data.get('id')

    if not container_id:
        print(f"[error] No container ID in response: {data}", file=sys.stderr)
        return None

    print(f"[success] Media container created: {container_id}")
    return container_id

def check_container_status(account_id, access_token, container_id):
    """Check if the media container is ready for publishing."""
    url = f"{GRAPH_API_BASE}/{container_id}"

    params = {
        'fields': 'status_code,status',
        'access_token': access_token
    }

    max_attempts = 30  # Increase attempts
    for attempt in range(max_attempts):
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"[warn] Status check failed: {response.status_code}", file=sys.stderr)
            time.sleep(3)
            continue

        data = response.json()
        status = data.get('status_code')
        status_msg = data.get('status', '')

        print(f"[info] Container status: {status} {status_msg} (attempt {attempt + 1}/{max_attempts})")

        if status == 'FINISHED':
            # Wait a bit more after FINISHED to ensure Instagram is truly ready
            print(f"[info] Waiting 10 seconds for Instagram to finalize...")
            time.sleep(10)
            print(f"[success] Container ready for publishing")
            return True
        elif status == 'ERROR':
            print(f"[error] Container processing failed: {data}", file=sys.stderr)
            return False
        elif status == 'IN_PROGRESS':
            time.sleep(3)
        elif status == 'EXPIRED':
            print(f"[error] Container expired", file=sys.stderr)
            return False
        else:
            # Unknown status, wait and retry
            time.sleep(3)

    print(f"[error] Container processing timed out", file=sys.stderr)
    return False

def publish_media(account_id, access_token, container_id):
    """Publish the media container to Instagram."""
    url = f"{GRAPH_API_BASE}/{account_id}/media_publish"

    params = {
        'creation_id': container_id,
        'access_token': access_token
    }

    print(f"[info] Publishing to Instagram...")

    response = requests.post(url, params=params)

    if response.status_code != 200:
        print(f"[error] Failed to publish: {response.status_code}", file=sys.stderr)
        print(f"[error] Response: {response.text}", file=sys.stderr)
        return None

    data = response.json()
    media_id = data.get('id')

    if not media_id:
        print(f"[error] No media ID in response: {data}", file=sys.stderr)
        return None

    print(f"[success] Published to Instagram! Media ID: {media_id}")
    return media_id

def main():
    print("[info] Starting Instagram post...")
    print(f"[info] Graph API version: {GRAPH_API_VERSION}")

    # Get credentials
    access_token, account_id = get_env_vars()
    print(f"[info] Account ID: {account_id}")
    print(f"[info] Token length: {len(access_token)} chars")

    # Load emoji data
    data = load_emoji_data()
    timestamp = data.get('timestamp', data.get('date', date.today().isoformat()))
    post_type = data.get('post_type', 'normal')
    print(f"[info] Posting emojis for {timestamp}")
    print(f"[info] Post type: {post_type}")

    # Check if already posted this timestamp (skip duplicate check for essence posts)
    if post_type != 'essence' and was_already_posted(timestamp):
        print(f"[info] Already posted for {timestamp}, skipping to avoid duplicate")
        print("[done] No action needed")
        return 0

    if post_type == 'essence':
        print(f"[info] Essence post - skipping duplicate check, will post regardless")

    # Get image URL
    image_url = get_image_url(data)
    print(f"[info] Image URL: {image_url}")

    # Verify image is accessible
    print(f"[info] Verifying image is accessible...")
    if not verify_image_accessible(image_url):
        print("[error] Image not accessible, cannot post to Instagram", file=sys.stderr)
        sys.exit(1)

    # Generate caption
    caption = generate_caption(data)
    print(f"[info] Caption generated ({len(caption)} chars)")
    print(f"[info] Caption preview: {caption[:100]}...")

    # Create media container
    container_id = create_media_container(account_id, access_token, image_url, caption)
    if not container_id:
        print("[error] Failed to create media container", file=sys.stderr)
        sys.exit(1)

    # Wait for container to be ready
    if not check_container_status(account_id, access_token, container_id):
        print("[error] Container not ready for publishing", file=sys.stderr)
        sys.exit(1)

    # Publish
    media_id = publish_media(account_id, access_token, container_id)
    if not media_id:
        print("[error] Failed to publish to Instagram", file=sys.stderr)
        sys.exit(1)

    # Mark as posted to prevent duplicates (only for normal posts)
    if post_type != 'essence':
        mark_as_posted(timestamp, media_id)
        print(f"[info] Marked {timestamp} as posted (normal post)")
    else:
        print(f"[info] Essence post - not logging to prevent duplicate tracking")

    print(f"\n[done] Successfully posted to Instagram!")
    print(f"[info] View at: https://instagram.com/todayinemojis")

    return 0

if __name__ == "__main__":
    sys.exit(main())
