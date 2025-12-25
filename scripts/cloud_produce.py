#!/usr/bin/env python3
"""
Cloud Producer - Python Wrapper

This script wraps the existing emoji generation logic and sends the result
to the cloud TypeScript producer for storage in GCP.

Usage:
    python scripts/cloud_produce.py --type=normal
    python scripts/cloud_produce.py --type=essence
    python scripts/cloud_produce.py --type=normal --dry-run
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import date
from pathlib import Path

# Import existing scripts
sys.path.insert(0, str(Path(__file__).parent))
import update_emojis_ai
import prepare_daily_post
import generate_emoji_image

INPUT_FILE = "public/data/today.json"
CLOUD_PRODUCER_SCRIPT = "src/cloud/cli/produce.ts"

RSS_SOURCES = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com&ceid=US:en&hl=en-US&gl=US",
    "https://www.theguardian.com/world/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
]


def run_emoji_selection():
    """Run AI emoji selection"""
    print("[info] Running AI emoji selection...")
    result = update_emojis_ai.main()
    if result != 0:
        raise RuntimeError("AI emoji selection failed")


def run_prepare_post():
    """Run prepare daily post (determines type and adds essence if needed)"""
    print("[info] Preparing daily post...")
    result = prepare_daily_post.main()
    if result != 0:
        raise RuntimeError("Prepare daily post failed")


def load_today_data():
    """Load today.json"""
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_image(data):
    """Generate image and return path"""
    print("[info] Generating image...")

    # Get the generated image path from generate_emoji_image
    # We need to modify generate_emoji_image.py to return the path
    # For now, we'll construct it manually
    today = data.get("date", date.today().isoformat())
    from datetime import datetime
    now = datetime.utcnow()
    timestamp = now.strftime("%H%M")
    image_filename = f"{today}-{timestamp}.png"
    image_path = f"public/images/daily/{image_filename}"

    # Run the image generation (clear sys.argv to avoid argument conflicts)
    saved_argv = sys.argv
    try:
        sys.argv = ['generate_emoji_image.py']
        result = generate_emoji_image.main()
        if result != 0:
            raise RuntimeError("Image generation failed")
    finally:
        sys.argv = saved_argv

    # Find the most recently generated image
    import glob
    images = sorted(glob.glob("public/images/daily/*.png"), key=os.path.getmtime, reverse=True)
    if not images:
        raise FileNotFoundError("No generated image found")

    return images[0]


def read_image_buffer(image_path):
    """Read image file as buffer"""
    with open(image_path, "rb") as f:
        return f.read()


def send_to_cloud(data, image_path, dry_run=False):
    """Send edition data to cloud producer (TypeScript)"""
    print("[info] Sending edition to cloud...")

    # Read image as base64 for JSON transport
    import base64
    image_buffer = read_image_buffer(image_path)
    image_base64 = base64.b64encode(image_buffer).decode('utf-8')

    # Build producer input
    producer_input = {
        "date": data.get("date", date.today().isoformat()),
        "post_type": data.get("post_type", "normal"),
        "emojis": data.get("emojis"),
        "essence": data.get("essence"),
        "image_buffer_base64": image_base64,
        "rss_sources": RSS_SOURCES,
        "model": "gpt-4o-mini",
        "provider": "openai",
    }

    # Write to temp file for TypeScript to read
    temp_input = "/tmp/cloud_producer_input.json"
    with open(temp_input, "w", encoding="utf-8") as f:
        json.dump(producer_input, f)

    # Call TypeScript producer via Node.js
    env = os.environ.copy()
    if dry_run:
        env["CLOUD_DRY_RUN"] = "true"

    # Ensure critical environment variables are set
    required_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "CLOUD_STORAGE_BUCKET",
    ]
    missing_vars = [var for var in required_vars if not env.get(var)]
    if missing_vars and not dry_run:
        print(f"[warn] Missing environment variables: {', '.join(missing_vars)}", file=sys.stderr)
        print(f"[warn] Make sure to set them or source .env.local", file=sys.stderr)

    try:
        # Use tsx to run TypeScript directly (requires: npm install -g tsx)
        result = subprocess.run(
            ["npx", "tsx", CLOUD_PRODUCER_SCRIPT, temp_input],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"[error] Cloud producer failed: {e}", file=sys.stderr)
        print(e.stdout, file=sys.stdout)
        print(e.stderr, file=sys.stderr)
        raise
    finally:
        # Cleanup temp file
        if os.path.exists(temp_input):
            os.unlink(temp_input)


def main():
    parser = argparse.ArgumentParser(description="Cloud producer for Today in Emojis")
    parser.add_argument("--type", choices=["normal", "essence", "auto"], default="auto",
                      help="Post type (auto determines based on cadence)")
    parser.add_argument("--dry-run", action="store_true",
                      help="Dry-run mode (no cloud writes)")
    args = parser.parse_args()

    try:
        # Step 1: Run AI emoji selection
        run_emoji_selection()

        # Step 2: Prepare post (determines if essence or normal)
        run_prepare_post()

        # Step 3: Load the prepared data
        data = load_today_data()
        post_type = data.get("post_type", "normal")

        print(f"[info] Post type determined: {post_type}")

        # Step 4: Generate image
        image_path = generate_image(data)
        print(f"[info] Image generated: {image_path}")

        # Step 5: Send to cloud
        send_to_cloud(data, image_path, dry_run=args.dry_run)

        print("[info] ✓ Cloud production complete!")
        return 0

    except Exception as e:
        print(f"[error] Cloud production failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
