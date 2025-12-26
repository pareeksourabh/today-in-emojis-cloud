# Cloud Producer Dockerfile
# This container runs the cloud producer to generate editions and upload to GCP

FROM node:20-slim

# Install Python 3 and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    fonts-noto-color-emoji \
    imagemagick \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install Node.js dependencies
RUN npm ci --only=production

# Install TypeScript execution tool
RUN npm install -g tsx

# Copy Python requirements (if we had a requirements.txt)
# For now, install dependencies directly
# Use --break-system-packages for Python 3.11+ in containerized environment
RUN pip3 install --no-cache-dir --break-system-packages \
    feedparser \
    pillow \
    requests \
    playwright

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY public/ ./public/
COPY data/ ./data/

# Create output directories
RUN mkdir -p public/images/daily
RUN mkdir -p public/data

# Set environment variables
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Default to normal mode
# Must be overridden by Cloud Scheduler to POST_TYPE=essence for essence jobs
ENV POST_TYPE=normal

# Default command - reads POST_TYPE from environment
CMD ["sh", "-c", "python3 scripts/cloud_produce.py --type=${POST_TYPE}"]
