/**
 * Cloud Producer
 *
 * Main entry point for cloud-based edition generation.
 * This runs independently of the GitHub workflow and stores editions in the cloud.
 */

import { CloudEdition } from './schema/edition';
import { uploadImage } from './storage';
import { writeEdition, getEditionsByDate } from './database';
import { getCloudConfig } from './config';

/**
 * Producer input (comes from existing Python scripts via wrapper)
 */
export interface ProducerInput {
  date: string;                    // YYYY-MM-DD
  post_type: 'normal' | 'essence';
  emojis?: Array<{
    char: string;
    label: string;
    title: string;
    summary: string;
    url: string;
  }>;
  essence?: {
    emotion_label: string;
    emoji: string;
    rationale: string;
    palette: string[];
    temperature: number;
    fallback: boolean;
  };
  image_buffer: Buffer;            // Generated image
  rss_sources: string[];
  model: string;
  provider: string;
}

/**
 * Generate edition ID
 */
function generateEditionId(date: string, postType: 'normal' | 'essence', sequenceIndex: number): string {
  if (postType === 'essence') {
    return `${date}-essence`;
  }
  return `${date}-normal-${sequenceIndex}`;
}

/**
 * Produce a single edition and store it in the cloud
 */
export async function produceEdition(input: ProducerInput): Promise<CloudEdition> {
  const config = getCloudConfig();
  const timestamp = new Date().toISOString();

  // Calculate sequence index from existing editions for this date
  const todayEditions = await getEditionsByDate(input.date);
  const normalPostsToday = todayEditions.filter(e => e.post_type === 'normal').length;
  const sequenceIndex = input.post_type === 'normal' ? normalPostsToday + 1 : 1;

  // Generate edition ID
  const editionId = generateEditionId(input.date, input.post_type, sequenceIndex);

  console.log(`[info] Producing edition: ${editionId}`);
  console.log(`[info] Post type: ${input.post_type}`);

  // Upload image to cloud storage
  const uploadResult = await uploadImage(
    input.image_buffer,
    input.date,
    input.post_type,
    input.post_type === 'normal' ? sequenceIndex : undefined
  );

  // Build edition object
  const edition: CloudEdition = {
    edition_id: editionId,
    date: input.date,
    timestamp,
    post_type: input.post_type,
    emojis: input.post_type === 'normal' ? input.emojis : undefined,
    essence: input.post_type === 'essence' ? input.essence : undefined,
    assets: {
      image_url: uploadResult.url,
      image_path: uploadResult.path,
      expires_at: uploadResult.expiresAt,
    },
    source_meta: {
      rss_sources: input.rss_sources,
      model: input.model,
      provider: input.provider,
      created_at: timestamp,
    },
  };

  // Write to Firestore
  await writeEdition(edition);

  console.log(`[info] Edition produced successfully: ${editionId}`);
  console.log(`[info] Image URL: ${uploadResult.url}`);

  return edition;
}

/**
 * Get the total number of editions for today
 */
export async function getTodayEditionCount(date: string): Promise<number> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log(`[DRY-RUN] Would query edition count for ${date}`);
    return 0;
  }

  const editions = await getEditionsByDate(date);
  return editions.length;
}

/**
 * Health check - verify all cloud services are accessible
 */
export async function healthCheck(): Promise<boolean> {
  console.log('[info] Running cloud services health check...');

  const { checkBucketAccess } = await import('./storage');
  const { checkDatabaseAccess } = await import('./database');

  const bucketOk = await checkBucketAccess();
  const databaseOk = await checkDatabaseAccess();

  const healthy = bucketOk && databaseOk;

  if (healthy) {
    console.log('[info] ✓ All cloud services are healthy');
  } else {
    console.error('[error] ✗ Some cloud services are not accessible');
  }

  return healthy;
}
