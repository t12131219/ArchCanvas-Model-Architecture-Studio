// Current formal renderer observations only. Expected roles, SVG, geometry,
// provenance and browser acceptance belong to a separate independent oracle.
import { readdirSync, readFileSync, mkdirSync, writeFileSync, statSync, realpathSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildScene, buildExportScene, renderSvg } from '../../../../studio/src/core/index.ts';
import type { CanvasDocument, ExportSceneOptions } from '../../../../studio/src/core/types.ts';

interface Binding { path: string; bytes: number; sha256: string }
const helper = realpathSync(fileURLToPath(import.meta.url));
const root = realpathSync(resolve(dirname(helper), '../../../..'));
const cli = new Map<string, string>();
for (let index = 2; index < process.argv.length; index += 2) {
  const key = process.argv[index], value = process.argv[index + 1];
  if (!['--raw', '--output', '--case-count', '--build-receipt'].includes(key) || !value || cli.has(key)) throw new Error('Use --raw DIR --output FRESH_DIR --case-count N --build-receipt FILE');
  cli.set(key, value);
}
for (const key of ['--raw', '--output', '--case-count', '--build-receipt']) if (!cli.has(key)) throw new Error(`Missing ${key}`);
const raw = realpathSync(resolve(cli.get('--raw')!)), output = resolve(cli.get('--output')!);
const buildReceipt = realpathSync(resolve(cli.get('--build-receipt')!));
const caseCount = Number(cli.get('--case-count'));
if (!Number.isSafeInteger(caseCount) || caseCount <= 0) throw new Error('case-count must be a positive integer');
if (output === raw || output.startsWith(raw + '/') || raw.startsWith(output + '/')) throw new Error('Raw and output trees must be separate');
const fingerprint = (path: string): Binding => {
  const bytes = readFileSync(path), rel = relative(root, path);
  return { path: rel.startsWith('../') ? path : rel, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
};
const walk = (directory: string): string[] => readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
  const path = join(directory, entry.name);
  if (entry.isSymbolicLink()) throw new Error(`Do not silently follow symlink inputs: ${path}`);
  return entry.isDirectory() ? walk(path) : entry.isFile() ? [path] : [];
}).sort();
const inputPaths = () => [...new Set([
  ...walk(join(root, 'studio/src')),
  ...walk(join(root, 'studio/dist')),
  ...walk(raw), helper, buildReceipt, realpathSync(process.execPath),
  ...['package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts'].map(name => join(root, 'studio', name)),
])].sort();
const cases = readdirSync(raw, { withFileTypes: true }).filter(entry => entry.isDirectory() && /^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(entry.name) &&
  statSync(join(raw, entry.name, 'document.json'), { throwIfNoEntry: false })?.isFile()).map(entry => entry.name).sort();
if (cases.length !== caseCount) throw new Error(`Require ${caseCount} actual raw case documents; found ${cases.length}`);
const pathsBefore = inputPaths(), inputsBefore = pathsBefore.map(fingerprint);
const build = JSON.parse(readFileSync(buildReceipt, 'utf8')) as {
  kind?: string; exitCode?: number; sourceBeforeAfterExact?: boolean; inputsAfter?: Binding[]; builtFiles?: Binding[];
};
if (build.kind !== 'build' || build.exitCode !== 0 || build.sourceBeforeAfterExact !== true || !build.inputsAfter?.length || !build.builtFiles?.length) throw new Error('Require an actual successful, source-stable build receipt');
const buildBound = [...build.inputsAfter, ...build.builtFiles].filter(binding => binding.path.startsWith('studio/src/') || binding.path.startsWith('studio/dist/') ||
  ['studio/package.json', 'studio/package-lock.json', 'studio/tsconfig.json', 'studio/vite.config.ts'].includes(binding.path));
for (const binding of buildBound) if (JSON.stringify(fingerprint(resolve(root, binding.path))) !== JSON.stringify(binding)) throw new Error(`Current renderer/build differs from successful receipt: ${binding.path}`);

mkdirSync(output); // Exclusive: existing partial runs are never overwritten.
const startedAt = new Date().toISOString(), records: object[] = [];
writeFileSync(join(output, 'preparation.json'), JSON.stringify({
  protocol: 'archcanvas-monochrome-current-observation/1', purpose: 'Current renderer observations; not expected results or independent acceptance',
  startedAt, argv: process.argv, cwd: process.cwd(), root, raw, output, cases, inputsBefore,
  buildReceipt: fingerprint(buildReceipt), currentRendererBuildBindings: buildBound,
  modelsExecuted: false, dependenciesInstalled: false,
}, null, 2) + '\n', { flag: 'wx' });
try {
  for (const caseId of cases) {
    const directory = join(raw, caseId), input = join(directory, 'document.json');
    const document = JSON.parse(readFileSync(input, 'utf8')) as CanvasDocument, untouched = JSON.stringify(document);
    const exportReceiptPath = join(directory, 'figure.svg.receipt.json');
    let options: ExportSceneOptions = {}, exportOptionsSource: string | null = null;
    if (statSync(exportReceiptPath, { throwIfNoEntry: false })?.isFile()) {
      const receipt = JSON.parse(readFileSync(exportReceiptPath, 'utf8')) as {
        widthMm?: number; exportScope?: { kind?: string; selectedNodeId?: string };
      };
      if (receipt.widthMm !== undefined) options.widthMm = receipt.widthMm;
      if (receipt.exportScope?.kind === 'detail') {
        if (!receipt.exportScope.selectedNodeId) throw new Error(`Actual detail receipt lacks selectedNodeId: ${caseId}`);
        options.nodeId = receipt.exportScope.selectedNodeId;
      } else if (receipt.exportScope?.kind !== undefined && receipt.exportScope.kind !== 'document') throw new Error(`Unknown actual export scope: ${caseId}`);
      exportOptionsSource = fingerprint(exportReceiptPath).path;
    }
    const scene = buildScene(document), exported = buildExportScene(document, options);
    if (JSON.stringify(document) !== untouched) throw new Error(`Renderer mutated observed document: ${caseId}`);
    const target = join(output, caseId); mkdirSync(target);
    const bodies: Record<string, string> = {
      'scene.json': JSON.stringify(scene, null, 2) + '\n', 'export.scene.json': JSON.stringify(exported, null, 2) + '\n',
      'interactive.svg': renderSvg(scene, { interactive: true }), 'publication.svg': renderSvg(exported),
    };
    for (const [name, body] of Object.entries(bodies)) writeFileSync(join(target, name), body, { flag: 'wx' });
    records.push({ caseId, input: fingerprint(input), exportOptions: options, exportOptionsSource,
      documentId: document.id, revision: document.revision, sourceDigest: document.architecture.sourceDigest, irDigest: document.architecture.irDigest,
      fullSceneNodeCount: scene.nodes.length, fullSceneEdgeCount: scene.edges.length,
      exportSceneNodeCount: exported.nodes.length, exportSceneEdgeCount: exported.edges.length,
      documentInMemoryUnchanged: true, files: Object.keys(bodies).map(name => fingerprint(join(target, name))) });
  }
  const pathsAfter = inputPaths(), inputsAfter = pathsAfter.map(fingerprint);
  const inputSetAndBytesUnchanged = JSON.stringify(pathsBefore) === JSON.stringify(pathsAfter) && JSON.stringify(inputsBefore) === JSON.stringify(inputsAfter);
  if (!inputSetAndBytesUnchanged) throw new Error('Current renderer/source/build or raw inputs changed during observations');
  writeFileSync(join(output, 'receipt.json'), JSON.stringify({
    protocol: 'archcanvas-monochrome-current-observation/1', startedAt, finishedAt: new Date().toISOString(), records,
    inputsBefore, inputsAfter, inputSetAndBytesUnchanged, argv: process.argv, cwd: process.cwd(),
    buildReceipt: fingerprint(buildReceipt), currentRendererBuildBindings: buildBound,
    scope: 'Trusted formal renderer observations only; no independent canonical, SVG, geometry, export, pixel, physical, human or performance acceptance implied.',
    modelsExecuted: false, dependenciesInstalled: false,
  }, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ caseCount: records.length, receipt: fingerprint(join(output, 'receipt.json')) }));
} catch (error) {
  writeFileSync(join(output, 'failure.json'), JSON.stringify({
    protocol: 'archcanvas-monochrome-current-observation/1', startedAt, failedAt: new Date().toISOString(), error: String(error),
    completedCaseRecords: records, inputsBefore, inputsAfterFailure: inputPaths().map(fingerprint),
    scope: 'Partial observations retained; this is not a successful observation receipt or independent acceptance.',
  }, null, 2) + '\n', { flag: 'wx' });
  throw error;
}
