#!/usr/bin/env node
/**
 * Cloud Producer CLI
 *
 * Command-line interface for producing editions to the cloud.
 * Called by Python wrapper script.
 */

import * as fs from 'fs';
import { produceEdition, healthCheck } from '../producer';
import type { ProducerInput } from '../producer';

interface CLIInput {
  date: string;
  post_type: 'normal' | 'essence';
  emojis?: any[];
  essence?: any;
  image_buffer_base64: string;
  rss_sources: string[];
  model: string;
  provider: string;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Usage: produce.ts <input-json-file>');
    console.error('       produce.ts --health-check');
    process.exit(1);
  }

  // Health check mode
  if (args[0] === '--health-check') {
    console.log('[info] Running health check...');
    const healthy = await healthCheck();
    process.exit(healthy ? 0 : 1);
  }

  // Production mode
  const inputFile = args[0];

  if (!fs.existsSync(inputFile)) {
    console.error(`[error] Input file not found: ${inputFile}`);
    process.exit(1);
  }

  try {
    // Read input
    const inputData: CLIInput = JSON.parse(fs.readFileSync(inputFile, 'utf-8'));

    // Convert base64 image to Buffer
    const imageBuffer = Buffer.from(inputData.image_buffer_base64, 'base64');

    // Build producer input
    const producerInput: ProducerInput = {
      date: inputData.date,
      post_type: inputData.post_type,
      emojis: inputData.emojis,
      essence: inputData.essence,
      image_buffer: imageBuffer,
      rss_sources: inputData.rss_sources,
      model: inputData.model,
      provider: inputData.provider,
    };

    // Produce edition
    const edition = await produceEdition(producerInput);

    console.log('[info] Edition produced successfully');
    console.log(JSON.stringify({
      edition_id: edition.edition_id,
      image_url: edition.assets.image_url,
      post_type: edition.post_type,
    }, null, 2));

    process.exit(0);
  } catch (error) {
    console.error('[error] Failed to produce edition:', error);
    process.exit(1);
  }
}

main();
