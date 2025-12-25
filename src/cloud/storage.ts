/**
 * Cloud Storage Client
 *
 * Handles uploading images to Google Cloud Storage with automatic 30-day lifecycle.
 */

import { Storage } from '@google-cloud/storage';
import { getCloudConfig } from './config';

export interface UploadResult {
  url: string;       // Public URL
  path: string;      // Storage path
  expiresAt: string; // ISO 8601 timestamp
}

/**
 * Upload an image to Cloud Storage
 */
export async function uploadImage(
  imageBuffer: Buffer,
  date: string,           // YYYY-MM-DD
  type: 'normal' | 'essence',
  index?: number          // Only for normal posts (1-5)
): Promise<UploadResult> {
  const config = getCloudConfig();

  // Generate storage path: YYYY/MM/DD/{type}-{index}.png
  const [year, month, day] = date.split('-');
  const filename = type === 'essence' ? 'essence.png' : `normal-${index}.png`;
  const path = `${year}/${month}/${day}/${filename}`;

  // Dry-run mode
  if (config.dryRun) {
    console.log(`[DRY-RUN] Would upload to: gs://${config.storageBucket}/${path}`);
    const mockUrl = `https://storage.googleapis.com/${config.storageBucket}/${path}`;
    const expiresAt = new Date(Date.now() + config.assetRetentionDays * 24 * 60 * 60 * 1000).toISOString();
    return { url: mockUrl, path, expiresAt };
  }

  // Initialize storage client
  const storage = new Storage({
    projectId: config.projectId,
    keyFilename: config.credentialsPath,
  });

  const bucket = storage.bucket(config.storageBucket);
  const file = bucket.file(path);

  // Upload file
  await file.save(imageBuffer, {
    contentType: 'image/png',
    metadata: {
      cacheControl: 'public, max-age=31536000', // 1 year (images are immutable)
    },
    public: true, // Make publicly accessible
  });

  // Get public URL
  const url = `https://storage.googleapis.com/${config.storageBucket}/${path}`;

  // Calculate expiration date
  const expiresAt = new Date(Date.now() + config.assetRetentionDays * 24 * 60 * 60 * 1000).toISOString();

  console.log(`[info] Uploaded image: ${url}`);
  console.log(`[info] Expires at: ${expiresAt}`);

  return { url, path, expiresAt };
}

/**
 * Set up bucket lifecycle policy (run once during setup)
 */
export async function setupBucketLifecycle(): Promise<void> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log('[DRY-RUN] Would set up lifecycle policy on bucket');
    return;
  }

  const storage = new Storage({
    projectId: config.projectId,
    keyFilename: config.credentialsPath,
  });

  const bucket = storage.bucket(config.storageBucket);

  // Set lifecycle rule to delete objects after N days
  await bucket.setMetadata({
    lifecycle: {
      rule: [
        {
          action: { type: 'Delete' },
          condition: { age: config.assetRetentionDays },
        },
      ],
    },
  });

  console.log(`[info] Bucket lifecycle policy set: delete after ${config.assetRetentionDays} days`);
}

/**
 * Check if bucket exists and is accessible
 */
export async function checkBucketAccess(): Promise<boolean> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log('[DRY-RUN] Skipping bucket access check');
    return true;
  }

  try {
    const storage = new Storage({
      projectId: config.projectId,
      keyFilename: config.credentialsPath,
    });

    const bucket = storage.bucket(config.storageBucket);
    const [exists] = await bucket.exists();

    if (!exists) {
      console.error(`[error] Bucket does not exist: ${config.storageBucket}`);
      return false;
    }

    console.log(`[info] Bucket accessible: ${config.storageBucket}`);
    return true;
  } catch (error) {
    console.error('[error] Failed to access bucket:', error);
    return false;
  }
}
