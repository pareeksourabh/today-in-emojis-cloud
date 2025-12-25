# Cloud Producer - Local Testing Guide

This guide explains how to test the cloud producer locally without making actual cloud writes.

---

## Prerequisites

1. **Install dependencies:**
   ```bash
   npm install
   pip install feedparser pillow requests
   ```

2. **Set environment variables for dry-run mode:**
   ```bash
   export CLOUD_DRY_RUN=true
   export OPENAI_API_KEY=your-key-here
   ```

---

## Dry-Run Mode

When `CLOUD_DRY_RUN=true`, the producer will:
- ✅ Generate emojis using AI
- ✅ Generate images locally
- ✅ Log what it would upload to cloud storage
- ✅ Log what it would write to Firestore
- ❌ NOT upload anything to GCP
- ❌ NOT write to Firestore

This allows you to test the full pipeline locally without cloud credentials.

---

## Local Testing Commands

### 1. Health Check
```bash
npm run cloud:health
```

This checks:
- Cloud storage bucket accessibility
- Firestore database connectivity

In dry-run mode, it skips actual checks and returns success.

### 2. Produce Normal Post (Dry-Run)
```bash
export CLOUD_DRY_RUN=true
python scripts/cloud_produce.py --type=auto --dry-run
```

This will:
1. Fetch news from RSS feeds
2. Ask AI to pick 5 emojis
3. Determine if this should be normal or essence (based on cadence)
4. Generate the image
5. Log what would be uploaded to cloud (but doesn't actually upload)

### 3. Produce Essence Post (Dry-Run)
```bash
export CLOUD_DRY_RUN=true
export ESSENCE_CADENCE_N=6  # Force it to be the 6th post
python scripts/cloud_produce.py --type=auto --dry-run
```

---

## Testing With Real Cloud (Requires GCP Credentials)

### 1. Set up GCP Service Account

Create a service account in GCP with these permissions:
- **Storage Admin** (for uploading images)
- **Cloud Datastore User** (for Firestore writes)

Download the JSON key file.

### 2. Set environment variables
```bash
export GOOGLE_CLOUD_PROJECT=today-in-emojis
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
export CLOUD_STORAGE_BUCKET=today-in-emojis-assets
export CLOUD_DRY_RUN=false
export OPENAI_API_KEY=your-key-here
```

### 3. Run producer (with real cloud writes)
```bash
python scripts/cloud_produce.py --type=auto
```

This will actually upload to GCP.

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `CLOUD_DRY_RUN` | Skip cloud writes (dry-run mode) | `false` |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `today-in-emojis` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON key | (none) |
| `CLOUD_STORAGE_BUCKET` | GCS bucket name for images | `today-in-emojis-assets` |
| `CLOUD_STORAGE_REGION` | GCS bucket region | `us-central1` |
| `FIRESTORE_DATABASE` | Firestore database ID | `(default)` |
| `FIRESTORE_COLLECTION` | Firestore collection name | `editions` |
| `ASSET_RETENTION_DAYS` | Auto-delete images after N days | `30` |
| `CLOUD_MODE` | Deployment mode | `parallel` |
| `OPENAI_API_KEY` | OpenAI API key for AI selection | (required) |
| `ESSENCE_CADENCE_N` | Cadence cycle (5+1 = 6) | `6` |

---

## Troubleshooting

### "Module not found: @google-cloud/storage"
Run: `npm install`

### "OPENAI_API_KEY is missing"
Set: `export OPENAI_API_KEY=your-key-here`

### "Image generation failed"
Make sure you have fonts installed:
```bash
# macOS - no action needed (uses Swift)
# Linux
sudo apt-get install fonts-noto-color-emoji
```

### "Permission denied" on GCP
Check that your service account has the correct IAM roles.

---

## Expected Output (Dry-Run)

```
[info] Running AI emoji selection...
[info] Fetched 40 headlines from RSS feeds
[info] AI selected 5 emojis
[info] Preparing daily post...
[info] Cadence: N=6, sequence_index=1 -> normal post
[info] Generating image...
[info] Image generated: public/images/daily/2025-12-24-0103.png
[info] Sending edition to cloud...
[info] Cloud configuration loaded:
  Project: today-in-emojis
  Bucket: today-in-emojis-assets
  Database: (default)
  Collection: editions
  Dry-run: true
  Mode: parallel
[info] Producing edition: 2025-12-24-normal-1
[info] Post type: normal
[info] Sequence: 1/6
[DRY-RUN] Would upload to: gs://today-in-emojis-assets/2025/12/24/normal-1.png
[DRY-RUN] Would write edition to Firestore:
{
  "edition_id": "2025-12-24-normal-1",
  "date": "2025-12-24",
  ...
}
[info] ✓ Cloud production complete!
```

---

## Next Steps

Once local testing is complete:
1. Set up GCP project and create bucket
2. Deploy as Cloud Run job with scheduler
3. Run in parallel mode for 7-14 days to validate
4. Cutover Instagram posting to cloud (Step 2)
5. Cutover website to cloud export (Step 3)
