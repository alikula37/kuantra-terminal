#!/usr/bin/env node

/**
 * Automated i18n Parity, Quality & UTF-8 Integrity Checker for Kuantra Terminal.
 * Verifies that:
 * 1. All translation keys match 100% across tr.json, en.json, and de.json.
 * 2. No empty strings or whitespace-only values exist.
 * 3. No UTF-8 encoding corruption (e.g. \ufffd, ??, or mangled question-mark tokens).
 * 4. Dynamic interpolation tokens ({param} or {{param}}) match 100% across all locales.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const LOCALES_DIR = path.resolve(__dirname, '../src/locales');
const REQUIRED_LOCALES = ['tr', 'en', 'de'];
const BASE_LOCALE = 'en';

function flattenObject(obj, prefix = '') {
  const result = {};
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      Object.assign(result, flattenObject(v, fullKey));
    } else {
      result[fullKey] = String(v);
    }
  }
  return result;
}

function extractInterpolationTokens(str) {
  const tokens = [];
  const regex = /\{+([a-zA-Z0-9_]+)\}+/g;
  let match;
  while ((match = regex.exec(str)) !== null) {
    tokens.push(match[1]);
  }
  return tokens.sort();
}

function runAudit() {
  console.log('🔍 [i18n-check] Initiating comprehensive tri-locale audit across [en, tr, de]...\n');

  const dictionaries = {};
  const rawContents = {};

  for (const loc of REQUIRED_LOCALES) {
    const filePath = path.join(LOCALES_DIR, `${loc}.json`);
    if (!fs.existsSync(filePath)) {
      console.error(`❌ [i18n-check] Missing dictionary file: ${filePath}`);
      process.exit(1);
    }
    try {
      const raw = fs.readFileSync(filePath, 'utf8');
      rawContents[loc] = raw;
      const parsed = JSON.parse(raw);
      dictionaries[loc] = flattenObject(parsed);
      console.log(`  -> ${loc.toUpperCase()}: ${Object.keys(dictionaries[loc]).length} synchronized keys`);
    } catch (err) {
      console.error(`❌ [i18n-check] Failed to parse JSON in ${filePath}:`, err.message);
      process.exit(1);
    }
  }

  let hasErrors = false;

  // 1. Key Parity Check
  const baseKeys = new Set(Object.keys(dictionaries[BASE_LOCALE]));
  for (const loc of REQUIRED_LOCALES) {
    if (loc === BASE_LOCALE) continue;
    const locKeys = new Set(Object.keys(dictionaries[loc]));

    const missingInLoc = [...baseKeys].filter((k) => !locKeys.has(k));
    const extraInLoc = [...locKeys].filter((k) => !baseKeys.has(k));

    if (missingInLoc.length > 0) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Missing ${missingInLoc.length} keys in '${loc}.json':`);
      missingInLoc.slice(0, 20).forEach((k) => console.error(`    - ${k}`));
      if (missingInLoc.length > 20) console.error(`    ... and ${missingInLoc.length - 20} more.`);
    }

    if (extraInLoc.length > 0) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Extra ${extraInLoc.length} unexpected keys in '${loc}.json':`);
      extraInLoc.slice(0, 20).forEach((k) => console.error(`    + ${k}`));
    }
  }

  // 2. Empty String & Whitespace Detection
  for (const loc of REQUIRED_LOCALES) {
    const emptyKeys = [];
    for (const [k, v] of Object.entries(dictionaries[loc])) {
      if (!v || v.trim().length === 0) {
        emptyKeys.push(k);
      }
    }
    if (emptyKeys.length > 0) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Found ${emptyKeys.length} empty or whitespace-only strings in '${loc}.json':`);
      emptyKeys.forEach((k) => console.error(`    - ${k}`));
    }
  }

  // 3. Encoding Corruption Scan
  for (const loc of REQUIRED_LOCALES) {
    const raw = rawContents[loc];
    const corruptedTokens = [];

    // Check for Unicode replacement character
    if (raw.includes('\ufffd')) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Found Unicode replacement character (\\ufffd) in '${loc}.json'`);
    }

    // Check for suspicious "??" or mangled Turkish/German strings (e.g. "Ba?lang??" or "K?M?LAT?F")
    for (const [k, v] of Object.entries(dictionaries[loc])) {
      if (v.includes('??') || /[a-zA-ZğüşıöçĞÜŞİÖÇ]\?[a-zA-ZğüşıöçĞÜŞİÖÇ]/.test(v)) {
        corruptedTokens.push({ key: k, value: v });
      }
    }

    if (corruptedTokens.length > 0) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Found ${corruptedTokens.length} corrupted encoding strings with '?' in '${loc}.json':`);
      corruptedTokens.slice(0, 10).forEach(({ key, value }) => console.error(`    - ${key}: "${value}"`));
    }
  }

  // 4. Interpolation Validator
  for (const loc of REQUIRED_LOCALES) {
    if (loc === BASE_LOCALE) continue;
    const mismatchedInterpolations = [];

    for (const [key, baseVal] of Object.entries(dictionaries[BASE_LOCALE])) {
      const locVal = dictionaries[loc][key];
      if (!locVal) continue;

      const baseTokens = extractInterpolationTokens(baseVal);
      const locTokens = extractInterpolationTokens(locVal);

      if (JSON.stringify(baseTokens) !== JSON.stringify(locTokens)) {
        mismatchedInterpolations.push({
          key,
          expected: baseTokens,
          found: locTokens,
        });
      }
    }

    if (mismatchedInterpolations.length > 0) {
      hasErrors = true;
      console.error(`\n❌ [i18n-check] Interpolation tokens mismatch in '${loc}.json':`);
      mismatchedInterpolations.forEach(({ key, expected, found }) => {
        console.error(`    - ${key}: expected [${expected.join(', ')}], found [${found.join(', ')}]`);
      });
    }
  }

  if (hasErrors) {
    console.error('\n🚨 [i18n-check] Validation FAILED: Fix all reported errors before building.\n');
    process.exit(1);
  }

  console.log(`\n✅ [i18n-check] 100% PARITY & UTF-8 INTEGRITY VERIFIED across all ${baseKeys.size} keys!`);
  console.log('   - 0 missing keys');
  console.log('   - 0 empty strings');
  console.log('   - 0 encoding corruption artifacts');
  console.log('   - 100% matching interpolation parameters\n');
}

runAudit();
