import { readFileSync, writeFileSync } from 'node:fs';
const source = readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8');
const target = new URL('../public/preview/ui-en.json', import.meta.url);
if (process.argv.includes('--check')) {
  if (readFileSync(target, 'utf8') !== source) throw Error('Preview UI dictionary differs from Studio dictionary. Run node scripts/sync-ui-locales.mjs.');
} else writeFileSync(target, source);
