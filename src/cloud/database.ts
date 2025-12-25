/**
 * Cloud Database Client (Firestore)
 *
 * Handles storing and retrieving edition data from Firestore.
 */

import { Firestore } from '@google-cloud/firestore';
import { getCloudConfig } from './config';
import { CloudEdition, EditionExport } from './schema/edition';

let firestoreInstance: Firestore | null = null;

/**
 * Get Firestore instance
 */
function getFirestore(): Firestore {
  if (!firestoreInstance) {
    const config = getCloudConfig();
    firestoreInstance = new Firestore({
      projectId: config.projectId,
      databaseId: config.firestoreDatabase,
      keyFilename: config.credentialsPath,
    });
  }
  return firestoreInstance;
}

/**
 * Remove undefined values from an object (Firestore doesn't support undefined)
 */
function removeUndefined(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(removeUndefined);
  }

  if (typeof obj === 'object') {
    const cleaned: any = {};
    for (const [key, value] of Object.entries(obj)) {
      if (value !== undefined) {
        cleaned[key] = removeUndefined(value);
      }
    }
    return cleaned;
  }

  return obj;
}

/**
 * Write an edition to Firestore
 */
export async function writeEdition(edition: CloudEdition): Promise<void> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log('[DRY-RUN] Would write edition to Firestore:');
    console.log(JSON.stringify(edition, null, 2));
    return;
  }

  const db = getFirestore();
  const collection = db.collection(config.firestoreCollection);
  const docRef = collection.doc(edition.edition_id);

  // Remove undefined values (Firestore doesn't support them)
  const cleanedEdition = removeUndefined(edition);

  await docRef.set(cleanedEdition);

  console.log(`[info] Edition written to Firestore: ${edition.edition_id}`);
}

/**
 * Read an edition from Firestore
 */
export async function readEdition(editionId: string): Promise<CloudEdition | null> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log(`[DRY-RUN] Would read edition from Firestore: ${editionId}`);
    return null;
  }

  const db = getFirestore();
  const collection = db.collection(config.firestoreCollection);
  const docRef = collection.doc(editionId);
  const doc = await docRef.get();

  if (!doc.exists) {
    console.log(`[warn] Edition not found: ${editionId}`);
    return null;
  }

  return doc.data() as CloudEdition;
}

/**
 * Get editions for a specific date
 */
export async function getEditionsByDate(date: string): Promise<CloudEdition[]> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log(`[DRY-RUN] Would query editions for date: ${date}`);
    return [];
  }

  const db = getFirestore();
  const collection = db.collection(config.firestoreCollection);

  const snapshot = await collection
    .where('date', '==', date)
    .orderBy('timestamp', 'asc')
    .get();

  if (snapshot.empty) {
    console.log(`[info] No editions found for date: ${date}`);
    return [];
  }

  const editions: CloudEdition[] = [];
  snapshot.forEach((doc) => {
    editions.push(doc.data() as CloudEdition);
  });

  console.log(`[info] Found ${editions.length} editions for date: ${date}`);
  return editions;
}

/**
 * Get editions for the last N days
 */
export async function getRecentEditions(days: number = 30): Promise<CloudEdition[]> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log(`[DRY-RUN] Would query last ${days} days of editions`);
    return [];
  }

  const db = getFirestore();
  const collection = db.collection(config.firestoreCollection);

  // Calculate cutoff date (N days ago)
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);
  const cutoffDateString = cutoffDate.toISOString().split('T')[0];

  const snapshot = await collection
    .where('date', '>=', cutoffDateString)
    .orderBy('date', 'desc')
    .orderBy('timestamp', 'desc')
    .get();

  if (snapshot.empty) {
    console.log(`[info] No editions found in last ${days} days`);
    return [];
  }

  const editions: CloudEdition[] = [];
  snapshot.forEach((doc) => {
    editions.push(doc.data() as CloudEdition);
  });

  console.log(`[info] Found ${editions.length} editions in last ${days} days`);
  return editions;
}

/**
 * Export editions to simplified format for website
 */
export function exportEditionsForWebsite(editions: CloudEdition[]): EditionExport[] {
  return editions.map((edition) => ({
    date: edition.date,
    post_type: edition.post_type,
    emojis: edition.emojis,
    essence: edition.essence
      ? {
          emotion_label: edition.essence.emotion_label,
          emoji: edition.essence.emoji,
          rationale: edition.essence.rationale,
        }
      : undefined,
    image_url: edition.assets.image_url,
  }));
}

/**
 * Check database connectivity
 */
export async function checkDatabaseAccess(): Promise<boolean> {
  const config = getCloudConfig();

  if (config.dryRun) {
    console.log('[DRY-RUN] Skipping database access check');
    return true;
  }

  try {
    const db = getFirestore();
    const collection = db.collection(config.firestoreCollection);

    // Try to list documents (limit 1 to minimize cost)
    await collection.limit(1).get();

    console.log(`[info] Database accessible: ${config.firestoreCollection}`);
    return true;
  } catch (error) {
    console.error('[error] Failed to access database:', error);
    return false;
  }
}
