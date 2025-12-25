# Today in Emojis - Cloud Producer

Cloud-based edition generator for [Today in Emojis](https://todayinemojis.com).

This repository contains the cloud infrastructure for producing daily emoji editions and storing them in Google Cloud Platform (Firestore + Cloud Storage).

## Architecture

- **Cloud Run**: Hosts the containerized producer service
- **Cloud Scheduler**: Triggers production jobs on a schedule
  - Normal posts: 5x daily (00:00, 04:00, 08:00, 12:00, 16:00 UTC)
  - Essence posts: 1x daily (20:00 UTC)
- **Firestore**: Stores edition metadata
- **Cloud Storage**: Hosts generated images with signed URLs

## Repository Structure

```
today-in-emojis-cloud/
├── src/cloud/           # TypeScript cloud producer
│   ├── config.ts        # Cloud configuration
│   ├── storage.ts       # Cloud Storage integration
│   ├── database.ts      # Firestore integration
│   ├── producer.ts      # Main producer logic
│   ├── schema/          # TypeScript schemas
│   └── cli/             # CLI entry point
├── scripts/             # Python scripts (shared with web repo)
│   ├── cloud_produce.py        # Main wrapper
│   ├── update_emojis_ai.py     # AI emoji selection
│   ├── prepare_daily_post.py   # Post preparation
│   └── generate_emoji_image.py # Image generation
├── docs/                # Documentation
│   ├── CLOUD_LOCAL_TESTING.md
│   └── CLOUD_RUN_DEPLOYMENT.md
├── Dockerfile           # Container definition
├── package.json         # Node.js dependencies
└── tsconfig.json        # TypeScript configuration
```

## Quick Start

### Prerequisites

1. **GCP Project Setup**:
   ```bash
   gcloud config set project today-in-emojis
   gcloud auth login
   ```

2. **Service Account**: Create and download service account key with permissions:
   - Cloud Storage Admin
   - Cloud Firestore User

3. **Environment Variables**:
   ```bash
   export GOOGLE_CLOUD_PROJECT=today-in-emojis
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
   export CLOUD_STORAGE_BUCKET=today-in-emojis-editions
   export OPENAI_API_KEY=your-openai-key
   ```

### Local Testing

```bash
# Install dependencies
npm install

# Health check
npm run cloud:health

# Dry run (no cloud writes)
export CLOUD_DRY_RUN=true
python3 scripts/cloud_produce.py --type=normal --dry-run

# Production run
python3 scripts/cloud_produce.py --type=normal
```

See [CLOUD_LOCAL_TESTING.md](docs/CLOUD_LOCAL_TESTING.md) for detailed instructions.

### Deploy to Cloud Run

```bash
# Build and push Docker image
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/today-in-emojis/today-in-emojis/cloud-producer:latest

# Deploy to Cloud Run
gcloud run deploy cloud-producer \
  --image us-central1-docker.pkg.dev/today-in-emojis/today-in-emojis/cloud-producer:latest \
  --platform managed \
  --region us-central1 \
  --no-allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=today-in-emojis,CLOUD_STORAGE_BUCKET=today-in-emojis-editions \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest

# Create Cloud Scheduler jobs
# Normal posts (5x daily)
for hour in 0 4 8 12 16; do
  gcloud scheduler jobs create http "cloud-producer-normal-${hour}" \
    --location us-central1 \
    --schedule "0 ${hour} * * *" \
    --uri "https://cloud-producer-XXXXX.run.app" \
    --http-method POST \
    --headers "Content-Type=application/json" \
    --message-body '{"type":"normal"}' \
    --oidc-service-account-email cloud-scheduler@today-in-emojis.iam.gserviceaccount.com
done

# Essence post (1x daily at 8pm UTC)
gcloud scheduler jobs create http "cloud-producer-essence" \
  --location us-central1 \
  --schedule "0 20 * * *" \
  --uri "https://cloud-producer-XXXXX.run.app" \
  --http-method POST \
  --headers "Content-Type=application/json" \
  --message-body '{"type":"essence"}' \
  --oidc-service-account-email cloud-scheduler@today-in-emojis.iam.gserviceaccount.com
```

See [CLOUD_RUN_DEPLOYMENT.md](docs/CLOUD_RUN_DEPLOYMENT.md) for complete deployment guide.

## How It Works

1. **Cloud Scheduler** triggers Cloud Run service with POST_TYPE (normal/essence)
2. **Cloud Run** container executes `cloud_produce.py`
3. **Python wrapper** orchestrates:
   - AI emoji selection (normal posts only)
   - Post preparation (adds essence metadata if needed)
   - Image generation
4. **TypeScript producer** uploads:
   - Image to Cloud Storage
   - Edition metadata to Firestore
5. **Results** returned with edition ID and image URL

## Post Types

### Normal Posts (5x daily)
- Selects 5 emojis representing current news
- Generated at: 00:00, 04:00, 08:00, 12:00, 16:00 UTC
- Edition ID format: `YYYY-MM-DD-normal-N` (N = 1-5)

### Essence Posts (1x daily)
- Analyzes day's emojis to create single-emoji summary
- Generated at: 20:00 UTC
- Edition ID format: `YYYY-MM-DD-essence`

## Relationship to Web Repo

This repository is separate from the main [today-in-emojis](https://github.com/pareeksourabh/today-in-emojis) web repository:

- **Web repo**: GitHub Actions workflows, Next.js site, GitHub Pages deployment
- **Cloud repo**: GCP infrastructure, cloud producer service

Both share the same core Python scripts (copied, not symlinked) for:
- `update_emojis_ai.py` - AI emoji selection
- `prepare_daily_post.py` - Post type and essence generation
- `generate_emoji_image.py` - Image rendering

## Development

```bash
# Install dependencies
npm install

# TypeScript compilation check
npx tsc --noEmit

# Run health check
npm run cloud:health

# Run producer locally
npm run cloud:produce
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account key | Yes |
| `CLOUD_STORAGE_BUCKET` | Cloud Storage bucket name | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `POST_TYPE` | Post type: `normal` or `essence` | Yes |
| `CLOUD_DRY_RUN` | Dry run mode (no cloud writes) | No |

## License

Same as main repository - ISC
