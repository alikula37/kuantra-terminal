#!/usr/bin/env node

/**
 * Automated i18n Parity Checker for Kuantra Terminal.
 * Verifies that all translation keys match 100% across tr.json, en.json, and de.json.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const LOCALES_DIR = path.resolve(__dirname, '../src/locales');
const REQUIRED_LOCALES = ['tr', 'en', 'de'];

function flattenKeys(obj, prefix = '') {
  let keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      keys = keys.concat(flattenKeys(v, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

function loadLocaleKeys(locale) {
  const filePath = path.join(LOCALES_DIR, `${locale}.json`);
  if (!fs.existsSync(filePath)) {
    console.error(`❌ [i18n-check] Missing dictionary file: ${filePath}`);
    process.exit(1);
  }
  try {
    const content = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return new Set(flattenKeys(content));
  } catch (err) {
    console.error(`❌ [i18n-check] Failed to parse JSON in ${filePath}:`, err.message);
    process.exit(1);
  }
}

function runCheck() {
  console.log('🔍 [i18n-check] Verifying localization dictionary parity across [tr, en, de]...');

  const dictionaries = {};
  for (const loc of REQUIRED_LOCALES) {
    dictionaries[loc] = loadLocaleKeys(loc);
    console.log(`  -> ${loc.toUpperCase()}: ${dictionaries[loc].size} unique keys`);
  }

  // Collect all unique keys across all dictionaries
  const allKeys = new Set();
  for (const keys of Object.values(dictionaries)) {
    for (const k of keys) {
      allKeys.add(k);
    }
  }

  let hasErrors = false;

  for (const loc of REQUIRED_LOCALES) {
    const missing = [];
    for (const k of allKeys) {
      if (!dictionaries[loc].has(k)) {
        missing.push(k);
      }
    }

    if (missing.length > 0) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Missing ${missing.length} keys in '${loc}.json':`);
      missing.slice(0, 30).forEach((k) => console.error(`    - ${k}`));
      if (missing.length > 30) {
        console.error(`    ... and ${missing.length - 30} more.`);
      }
    }
  }

  if (hasErrors) {
    console.error('\n🚨 [i18n-check] Build failed: Translation keys must be 100% synchronized across all locales.\n');
    process.exit(1);
  }

  console.log(`\n✅ [i18n-check] Parity verified! All ${allKeys.size} translation keys are 100% synchronized.\n`);
}

runCheck();
