#!/usr/bin/env node
/** Compile the independently served React update probe without changing the product build. */
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const studio = path.join(project, 'studio');
const evidence = path.join(project, 'docs/evidence/m4-hierarchy-optimization');
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--output' || !/^[a-z0-9][a-z0-9-]*$/.test(args[1]))) {
  throw new Error('Usage: node scripts/prepare_hierarchy_probe.mjs [--output lowercase-output-name]');
}
const outputName = args[1] ?? 'react-probe-dist';
const output = path.join(evidence, outputName);
const receiptPath = path.join(evidence, `${outputName}-prepare.json`);
const defaultReceipt = path.join(evidence, 'react-probe-prepare.json');
const exists = async target => { try { await stat(target); return true; } catch (error) { if (error.code === 'ENOENT') return false; throw error; } };
if (await exists(output) || await exists(receiptPath) || (outputName === 'react-probe-dist' && await exists(defaultReceipt))) {
  throw new Error('This output is already preserved. Select another --output name; never overwrite prior evidence.');
}
await mkdir(evidence, { recursive: true });
const temporaryRoot = await mkdtemp(path.join(studio, '.m4-hierarchy-probe-'));
const rel = target => path.relative(project, target).split(path.sep).join('/');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const sourceEntries = [];
async function binding(target, role) {
  const bytes = await readFile(target);
  const item = { path: rel(target), role, bytes: bytes.length, sha256: sha(bytes) };
  sourceEntries.push(item);
  return { bytes, item };
}
const startedAt = new Date().toISOString();
const receipt = {
  schemaVersion: 1, probe: 'actual-production-React-hierarchy-updates',
  status: 'preparing', startedAt, command: process.argv,
  projectRoot: project, temporaryCompileRoot: rel(temporaryRoot), outputDirectory: rel(output),
  mode: 'production', installsDependencies: false,
  sourceEntries, checks: {}, outputEntries: [],
  limits: ['This receipt confirms compilation and byte bindings, not an executed browser scenario.', 'Node property reads and exact DOM checks are available only after actual browser input. No FPS, paint, or input latency is measured.'],
};
try {
  const oldAppPath = path.join(project, 'docs/evidence/before-hierarchy-optimization/files/studio/src/App.tsx');
  const oldApp = await binding(oldAppPath, 'archived-formal-App-containing-legacy-TreeNode');
  const marker = Buffer.from('function TreeNode(');
  const functionStart = oldApp.bytes.lastIndexOf(marker);
  if (functionStart < 0) throw new Error('Archived formal TreeNode function was not found');
  const oldFunction = oldApp.bytes.subarray(functionStart);
  if (!oldFunction.toString().trimEnd().endsWith('}')) throw new Error('Archived formal TreeNode is not the final complete function');
  const prefix = Buffer.from("import type { Architecture, ArchitectureNode, CanvasDocument } from './core';\nimport { Icon } from './icons';\n\n");
  const suffix = Buffer.from('\nexport { TreeNode };\n');
  const legacy = Buffer.concat([prefix, oldFunction, suffix]);
  await writeFile(path.join(temporaryRoot, 'LegacyTree.tsx'), legacy);
  const currentTree = await binding(path.join(studio, 'src/HierarchyTree.tsx'), 'current-formal-HierarchyTree-copied-without-byte-changes');
  const icons = await binding(path.join(studio, 'src/icons.tsx'), 'formal-icons-copied-without-byte-changes');
  const coreTypes = await binding(path.join(studio, 'src/core/types.ts'), 'formal-types-copied-without-byte-changes');
  await writeFile(path.join(temporaryRoot, 'HierarchyTree.tsx'), currentTree.bytes);
  await writeFile(path.join(temporaryRoot, 'icons.tsx'), icons.bytes);
  await writeFile(path.join(temporaryRoot, 'core.ts'), coreTypes.bytes);
  await binding(path.join(studio, 'src/App.tsx'), 'current-formal-App-reference-only');
  await binding(path.join(studio, 'package.json'), 'formal-declared-dependencies');
  await binding(path.join(studio, 'package-lock.json'), 'formal-locked-dependencies');
  await binding(fileURLToPath(import.meta.url), 'probe-prepare-script');
  const support = path.join(project, 'scripts/m4_hierarchy_support');
  for (const name of ['index.html', 'main.tsx', 'probe.css']) {
    const source = await binding(path.join(support, name), `probe-support-${name}`);
    await writeFile(path.join(temporaryRoot, name), source.bytes);
  }
  const fixtureDir = path.join(project, 'docs/evidence/m4-current-native-diagnostic');
  const fixtureNames = (await readdir(fixtureDir)).filter(name => /^stress300-store.*\.json$/.test(name));
  if (fixtureNames.length !== 1) throw new Error(`Expected one frozen stress300 fixture, found ${fixtureNames.length}`);
  const fixture = await binding(path.join(fixtureDir, fixtureNames[0]), 'frozen-source-bound-Stress300-envelope');
  const parsed = JSON.parse(fixture.bytes.toString());
  if (parsed.document.architecture.nodes.length !== 304) throw new Error('Expected the current source-bound 304-node stress300 fixture');
  const publicDir = path.join(temporaryRoot, 'public');
  await mkdir(publicDir);
  await writeFile(path.join(publicDir, 'fixture.json'), fixture.bytes);
  const sourceBindings = {
    schemaVersion: 1, fixture: fixture.item, sourceEntries,
    legacyTreeExtraction: { source: oldApp.item, startByte: functionStart, endByteExclusive: oldApp.bytes.length, functionBytes: oldFunction.length, functionSha256: sha(oldFunction), completeExtractedBytesUnchanged: true, generatedModuleSha256: sha(legacy), generatedPrefix: prefix.toString(), generatedSuffix: suffix.toString() },
    currentHierarchySource: currentTree.item,
    copies: { hierarchyTreeSha256: sha(currentTree.bytes), iconSha256: sha(icons.bytes), coreTypesSha256: sha(coreTypes.bytes) },
  };
  await writeFile(path.join(publicDir, 'source-bindings.json'), JSON.stringify(sourceBindings, null, 2) + '\n');
  const tsconfig = {
    compilerOptions: { target: 'ES2022', lib: ['ES2022', 'DOM', 'DOM.Iterable'], module: 'ESNext', moduleResolution: 'bundler', jsx: 'react-jsx', strict: true, noEmit: true, skipLibCheck: true, types: ['vite/client', 'node'] },
    include: ['*.ts', '*.tsx'],
  };
  await writeFile(path.join(temporaryRoot, 'tsconfig.json'), JSON.stringify(tsconfig, null, 2) + '\n');
  const typescriptResult = spawnSync(process.execPath, [path.join(studio, 'node_modules/typescript/bin/tsc'), '--project', path.join(temporaryRoot, 'tsconfig.json')], { cwd: studio, encoding: 'utf8', env: { ...process.env } });
  await writeFile(path.join(evidence, `${outputName}-typecheck.txt`), (typescriptResult.stdout ?? '') + (typescriptResult.stderr ?? ''));
  receipt.typecheck = { exitCode: typescriptResult.status, signal: typescriptResult.signal, log: `docs/evidence/m4-hierarchy-optimization/${outputName}-typecheck.txt` };
  if (typescriptResult.error) throw typescriptResult.error;
  if (typescriptResult.status !== 0) throw new Error(`Probe strict TypeScript failed with exit ${typescriptResult.status}`);
  const vite = await import(pathToFileURL(path.join(studio, 'node_modules/vite/dist/node/index.js')).href);
  const react = await import(pathToFileURL(path.join(studio, 'node_modules/@vitejs/plugin-react/dist/index.js')).href);
  const logs = [];
  const logger = vite.createLogger('info', { allowClearScreen: false });
  for (const level of ['info', 'warn', 'error']) {
    const original = logger[level].bind(logger);
    logger[level] = (message, options) => { logs.push({ level, message }); original(message, options); };
  }
  try {
    await vite.build({ configFile: false, root: temporaryRoot, base: './', publicDir, plugins: [react.default()], customLogger: logger, build: { outDir: output, emptyOutDir: false, sourcemap: false, minify: true } });
  } finally {
    await writeFile(path.join(evidence, `${outputName}-vite-log.json`), JSON.stringify(logs, null, 2) + '\n');
  }
  const list = async root => {
    const entries = [];
    for (const entry of await readdir(root, { withFileTypes: true })) {
      const target = path.join(root, entry.name);
      if (entry.isDirectory()) entries.push(...await list(target));
      else if (entry.isFile()) { const bytes = await readFile(target); entries.push({ path: rel(target), bytes: bytes.length, sha256: sha(bytes) }); }
    }
    return entries.sort((a, b) => a.path.localeCompare(b.path));
  };
  const outputsBeforeBuildBinding = await list(output);
  const buildBindings = { schemaVersion: 1, outputDirectory: rel(output), compilationMode: 'production', outputs: outputsBeforeBuildBinding, sourceEntries, generatedLegacyModuleSha256: sha(legacy), limits: receipt.limits };
  await writeFile(path.join(output, 'build-bindings.json'), JSON.stringify(buildBindings, null, 2) + '\n');
  receipt.outputEntries = await list(output);
  const sourceAfter = await Promise.all(sourceEntries.map(async item => { const bytes = await readFile(path.join(project, item.path)); return { ...item, afterBytes: bytes.length, afterSha256: sha(bytes), unchanged: bytes.length === item.bytes && sha(bytes) === item.sha256 }; }));
  receipt.sourceRecheck = sourceAfter;
  receipt.checks = {
    strictTypesPassed: true,
    inputsUnchangedThroughoutCompilation: sourceAfter.every(item => item.unchanged),
    extractedLegacyFunctionIsRawArchivedBytes: legacy.subarray(prefix.length, prefix.length + oldFunction.length).equals(oldFunction),
    copiedNewComponentBytesEqualFormalSource: (await readFile(path.join(temporaryRoot, 'HierarchyTree.tsx'))).equals(currentTree.bytes),
    fixtureBytesEqualFrozenEnvelope: (await readFile(path.join(output, 'fixture.json'))).equals(fixture.bytes),
    standaloneOutputDoesNotDependOnStudioService: true,
  };
  if (!Object.values(receipt.checks).every(Boolean)) throw new Error('Source or output byte binding failed after compilation');
  receipt.status = 'compiled-not-browser-executed';
  receipt.finishedAt = new Date().toISOString();
  await writeFile(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
  if (outputName === 'react-probe-dist') await writeFile(defaultReceipt, JSON.stringify(receipt, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ status: receipt.status, outputDirectory: receipt.outputDirectory, receipt: rel(receiptPath), outputEntries: receipt.outputEntries.length, recommendedStaticServer: `python -m http.server 8890 --bind 127.0.0.1 --directory ${evidence}`, urlPath: `/${outputName}/` }, null, 2) + '\n');
} catch (error) {
  receipt.status = 'failed';
  receipt.error = { message: String(error), stack: error.stack ?? null };
  receipt.finishedAt = new Date().toISOString();
  await writeFile(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
  if (outputName === 'react-probe-dist') await writeFile(defaultReceipt, JSON.stringify(receipt, null, 2) + '\n');
  throw error;
}
