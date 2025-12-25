/**
 * Cloud Configuration
 *
 * Centralized configuration for all cloud services.
 * Uses environment variables for secrets and deployment-specific values.
 */

export interface CloudConfig {
  // GCP Project
  projectId: string;

  // Cloud Storage
  storageBucket: string;
  storageRegion: string;

  // Firestore
  firestoreDatabase: string;
  firestoreCollection: string;

  // Lifecycle
  assetRetentionDays: number;

  // Mode
  dryRun: boolean;
  mode: 'parallel' | 'instagram-cutover' | 'full-cutover';

  // Credentials
  credentialsPath?: string;
}

/**
 * Load configuration from environment variables
 */
export function loadCloudConfig(): CloudConfig {
  const config: CloudConfig = {
    // GCP Project
    projectId: process.env.GOOGLE_CLOUD_PROJECT || 'today-in-emojis',

    // Cloud Storage
    storageBucket: process.env.CLOUD_STORAGE_BUCKET || 'today-in-emojis-assets',
    storageRegion: process.env.CLOUD_STORAGE_REGION || 'us-central1',

    // Firestore
    firestoreDatabase: process.env.FIRESTORE_DATABASE || '(default)',
    firestoreCollection: process.env.FIRESTORE_COLLECTION || 'editions',

    // Lifecycle
    assetRetentionDays: parseInt(process.env.ASSET_RETENTION_DAYS || '30', 10),

    // Mode
    dryRun: process.env.CLOUD_DRY_RUN === 'true',
    mode: (process.env.CLOUD_MODE as CloudConfig['mode']) || 'parallel',

    // Credentials
    credentialsPath: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  };

  return config;
}

/**
 * Validate configuration
 */
export function validateConfig(config: CloudConfig): void {
  if (!config.projectId) {
    throw new Error('GOOGLE_CLOUD_PROJECT is required');
  }

  if (!config.storageBucket) {
    throw new Error('CLOUD_STORAGE_BUCKET is required');
  }

  if (!config.dryRun && !config.credentialsPath) {
    console.warn('[warn] GOOGLE_APPLICATION_CREDENTIALS not set. Using default credentials.');
  }

  if (config.assetRetentionDays < 1 || config.assetRetentionDays > 365) {
    throw new Error('ASSET_RETENTION_DAYS must be between 1 and 365');
  }

  console.log('[info] Cloud configuration loaded:');
  console.log(`  Project: ${config.projectId}`);
  console.log(`  Bucket: ${config.storageBucket}`);
  console.log(`  Database: ${config.firestoreDatabase}`);
  console.log(`  Collection: ${config.firestoreCollection}`);
  console.log(`  Dry-run: ${config.dryRun}`);
  console.log(`  Mode: ${config.mode}`);
}

/**
 * Get the default config instance
 */
let configInstance: CloudConfig | null = null;

export function getCloudConfig(): CloudConfig {
  if (!configInstance) {
    configInstance = loadCloudConfig();
    validateConfig(configInstance);
  }
  return configInstance;
}
