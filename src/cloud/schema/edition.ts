/**
 * Cloud Edition Schema
 *
 * This is the Source of Truth schema for all editions stored in the cloud.
 * GitHub repo will contain only exported subsets of this data.
 */

export interface CloudEdition {
  // Core identifiers
  edition_id: string;              // e.g., "2025-12-24-normal-1" or "2025-12-24-essence"
  date: string;                    // ISO 8601 date: "2025-12-24"
  timestamp: string;               // ISO 8601 timestamp: "2025-12-24T23:00:00.000Z"

  // Post type
  post_type: 'normal' | 'essence';

  // Content (normal posts only - undefined for essence)
  emojis?: EmojiItem[];

  // Content (essence posts only - undefined for normal)
  essence?: EssenceData;

  // Assets (cloud storage)
  assets: AssetMetadata;

  // Source metadata
  source_meta: SourceMetadata;
}

export interface EmojiItem {
  char: string;                    // Emoji character: "🏛️"
  label: string;                   // Short label: "louvre break-in shakes france"
  title: string;                   // Full headline
  summary: string;                 // Article summary (max 240 chars)
  url: string;                     // Source article URL
}

export interface EssenceData {
  emotion_label: string;           // e.g., "neutral", "hope", "anxiety"
  emoji: string;                   // Single emoji from palette
  rationale: string;               // 1-2 line explanation
  palette: string[];               // Allowed emoji palette used
  temperature: number;             // AI temperature setting
  fallback: boolean;               // True if AI call failed, using fallback
}

export interface AssetMetadata {
  image_url: string;               // Public URL: "https://storage.googleapis.com/..."
  image_path: string;              // Storage path: "2025/12/24/normal-1.png"
  expires_at: string;              // ISO 8601 (created_at + 30 days) - for assets only
}

export interface SourceMetadata {
  rss_sources: string[];           // RSS feed URLs queried (BBC, Reuters, Guardian, NYT)
  model: string;                   // AI model name: "gpt-4o-mini"
  provider: string;                // "openai"
  created_at: string;              // ISO 8601 timestamp
}

/**
 * Helper type for creating new editions
 */
export type CreateEditionInput = Omit<CloudEdition, 'edition_id' | 'timestamp' | 'assets'> & {
  image_buffer: Buffer;            // Image data to upload
};

/**
 * Export format for static website (last 30 days)
 */
export interface EditionExport {
  date: string;
  post_type: 'normal' | 'essence';
  emojis?: EmojiItem[];
  essence?: Pick<EssenceData, 'emotion_label' | 'emoji' | 'rationale'>;
  image_url: string;
}
