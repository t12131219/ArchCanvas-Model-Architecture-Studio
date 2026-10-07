// This reviewer reads current core observations and actual browser/export
// artifacts. Product functions never generate expected values here.
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import type { CanvasDocument, EdgeStyle, Scene } from '../../../../studio/src/core/types.ts';
import { assertCoverage, assertLegend, assertProtectedScene, assertStyles, assertSvgStyles, flatten, parseXml } from './oracle.ts';
import { assertEndpoints } from '../../m4-collapsed-residual-work/acceptance/oracle.ts';

const here = dirname(fileURLToPath(import.meta.url)), root = resolve(here, '../../../..');
type Binding = { path: string; bytes: number; sha256: string };
type PlanCase = { caseId: string; baselineKind: 'cnn12' | 'historical-transformer'; baselineCaseId: string;
  preset: 'paper' | 'monochrome'; widthMm: number; scope: { kind: 'document' } | { kind: 'detail'; nodeId: string };
  edgeStyleOverrides?: Record<string, EdgeStyle>; views: string[]; geometryReference?: 'matched-baseline' | 'frozen-journal' };
type Plan = { protocol: 'archcanvas-monochrome-role-browser-plan/1'; browserDirectory: string; coreDirectory: string;
  documentStoreDirectory: string; build: { js: Binding; css: Binding; index: Binding }; cases: PlanCase[];
  checkReceipts: { path: string; tests?: number }[]; journalReplayReceiptPath?: string };
const args = process.argv.slice(2);
assert.equal(args.length, 2, 'Usage: node --experimental-strip-types browser-readback.ts PLAN_JSON NEW_OUTPUT_DIRECTORY');
const safe = (path: string) => {
  const full = isAbsolute(path) ? resolve(path) : resolve(root, path);
  assert.ok(full.startsWith(root + '/'), `Input/output outside formal root ${path}`); return full;
};
const planPath = safe(args[0]), out = safe(args[1]); mkdirSync(out);
const inputs = new Map<string, Binding>();
const sha = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
function read(path: string) {
  const full = safe(path), bytes = readFileSync(full), binding = { path: relative(root, full), bytes: bytes.length, sha256: sha(bytes) };
  const previous = inputs.get(binding.path); if (previous) assert.deepEqual(binding, previous, `Input changed during audit ${binding.path}`);
  else inputs.set(binding.path, binding); return bytes;
}
const load = <T>(path: string): T => JSON.parse(read(path).toString());
const serial = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const write = (name: string, value: unknown) => writeFileSync(join(out, name), JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
const readTree = (directory: string) => {
  const files: string[] = [];
  for (const item of readdirSync(safe(directory), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const child = join(directory, item.name);
    if (item.isDirectory()) files.push(...readTree(child)); else { assert.ok(item.isFile()); read(child); files.push(child); }
  }
  return files;
};
const plan = load<Plan>(planPath); assert.equal(plan.protocol, 'archcanvas-monochrome-role-browser-plan/1');
assert.ok(plan.cases.length >= 9, 'Require full bounded role browser scope, not only one easy example');
assert.equal(new Set(plan.cases.map(item => item.caseId)).size, plan.cases.length);
for (const binding of Object.values(plan.build)) { read(binding.path); assert.deepEqual(inputs.get(binding.path), binding, 'Current asset identity'); }
for (const path of [fileURLToPath(import.meta.url), join(here, 'oracle.ts'), join(here, 'fixtures.ts'),
  join(here, 'acceptance-contract.final.json'), join(here, '../../m4-collapsed-residual-work/acceptance/oracle.ts')]) read(path);
readTree(join(here, 'baseline')); readTree(plan.browserDirectory); readTree(plan.coreDirectory);
const observed = load<{ protocol: string; inputSetAndBytesUnchanged: boolean; inputsBefore: Binding[]; inputsAfter: Binding[];
  records: { caseId: string; input: Binding; files: Binding[] }[]; modelsExecuted: boolean; dependenciesInstalled: boolean }>(join(plan.coreDirectory, 'receipt.json'));
assert.equal(observed.protocol, 'archcanvas-monochrome-current-observation/1'); assert.equal(observed.inputSetAndBytesUnchanged, true);
assert.equal(observed.modelsExecuted, false); assert.equal(observed.dependenciesInstalled, false); assert.deepEqual(observed.inputsBefore, observed.inputsAfter);
assert.deepEqual(observed.records.map(item => item.caseId).sort(), plan.cases.map(item => item.caseId).sort());
for (const binding of [...observed.inputsBefore, ...observed.records.flatMap(item => [item.input, ...item.files])]) {
  if (isAbsolute(binding.path) && !resolve(binding.path).startsWith(root + '/')) {
    assert.equal(resolve(binding.path), resolve(process.execPath), 'unexpected external observation input');
    const bytes = readFileSync(binding.path); assert.equal(bytes.length, binding.bytes); assert.equal(sha(bytes), binding.sha256);
  } else { read(binding.path); assert.deepEqual(inputs.get(binding.path), binding, 'core observation byte provenance'); }
}
type ReplayCase = { caseId: string; completeDocumentExact: boolean; actualDocumentPath: string; expectedDocument: Binding; expectedScene: Binding };
const replay = plan.journalReplayReceiptPath ? load<{ status: string; inputBytesUnchanged: boolean; inputsBefore: Binding[]; inputsAfter: Binding[]; cases: ReplayCase[] }>(plan.journalReplayReceiptPath) : null;
if (replay) {
  assert.equal(replay.status, 'bounded-pass'); assert.equal(replay.inputBytesUnchanged, true); assert.deepEqual(replay.inputsBefore, replay.inputsAfter);
  for (const binding of [...replay.inputsBefore, ...replay.cases.flatMap(item => [item.expectedDocument, item.expectedScene])]) {
    read(binding.path); assert.deepEqual(inputs.get(binding.path), binding, 'frozen journal replay input/output no longer exact');
  }
}
const historicalByteCopies = load<{ originalBinding: Binding; exactHistoricalCopy: Binding }>(join(here, 'post-check-byte-preservation/receipt.json'));
read(historicalByteCopies.exactHistoricalCopy.path);
assert.deepEqual(inputs.get(historicalByteCopies.exactHistoricalCopy.path), historicalByteCopies.exactHistoricalCopy);
const checks = plan.checkReceipts.map(item => {
  const receipt = load<Record<string, unknown>>(item.path); assert.equal(receipt.exitCode, 0); assert.equal(receipt.sourceBeforeAfterExact, true);
  const before = receipt.inputsBefore as Binding[], after = receipt.inputsAfter as Binding[];
  assert.deepEqual(before, after, 'Root check inputs changed');
  for (const binding of before) {
    if (isAbsolute(binding.path) && !resolve(binding.path).startsWith(root + '/')) continue; // host infrastructure belongs to its root receipt
    read(binding.path);
    const current = inputs.get(relative(root, safe(binding.path)));
    if (JSON.stringify(current) !== JSON.stringify(binding)) {
      assert.deepEqual(binding, historicalByteCopies.originalBinding, 'Unexpected checked executable/fixture/source change');
      assert.equal(binding.bytes, historicalByteCopies.exactHistoricalCopy.bytes); assert.equal(binding.sha256, historicalByteCopies.exactHistoricalCopy.sha256);
    }
  }
  const stdoutPath = join(dirname(item.path), 'stdout.txt'), stdout = read(stdoutPath).toString();
  const stderr = read(join(dirname(item.path), 'stderr.txt')).toString();
  if (item.tests !== undefined) {
    if (receipt.protocol === 'archcanvas-mono-publication-check/1') {
      assert.match(stderr, new RegExp(`Ran ${item.tests} tests in `)); assert.match(stderr, /\nOK\s*$/);
      assert.equal((stderr.match(/\.\.\. ok\n/g) ?? []).length, item.tests, 'actual Python individual test successes');
    } else {
      for (const [label, count] of [['tests', item.tests], ['pass', item.tests], ['fail', 0], ['skipped', 0]])
        assert.match(stdout, new RegExp(`(?:ℹ|#)\\s+${label}\\s+${count}(?:\\s|$)`), `Actual ${label} count`);
    }
  }
  return { path: item.path, exitCode: 0, tests: item.tests ?? null, exactInputsAtCheck: before.length,
    historicalDocumentationResolution: historicalByteCopies, currentProductAndTestInputsExact: true };
});
const results: unknown[] = [], numberExceptions: unknown[] = [];

function canonicalTree(value: ReturnType<typeof parseXml>): unknown {
  return { name: value.name, attributes: value.attributes,
    text: value.name === 'metadata' ? JSON.parse(value.text) : value.text.trim() ? value.text : '',
    children: value.children.map(canonicalTree) };
}
function dimensions(scene: Scene, svg: string) {
  const tree = parseXml(svg), vb = tree.attributes.viewBox.split(/\s+/).map(Number);
  assert.deepEqual(vb, ['x', 'y', 'width', 'height'].map(key => scene.bounds[key as keyof Scene['bounds']]));
  const metadata = JSON.parse(flatten(tree).find(item => item.name === 'metadata')!.text);
  const height = scene.pageSpec.widthMm * vb[3] / vb[2];
  assert.ok(Math.abs(Number(tree.attributes.width.replace(/mm$/, '')) - scene.pageSpec.widthMm) <= .011);
  assert.ok(Math.abs(Number(tree.attributes.height.replace(/mm$/, '')) - height) <= .011);
  assert.ok(Math.abs(metadata.heightMm - height) <= 1e-10); assert.equal(metadata.widthMm, scene.pageSpec.widthMm);
  return { widthMm: scene.pageSpec.widthMm, heightMm: height, viewBox: vb };
}
function actualExport(directory: string, document: CanvasDocument, scene: Scene, publication: string, expectedUuid: string) {
  const actual = read(join(directory, 'figure.svg')), receipt = load<Record<string, unknown>>(join(directory, 'figure.svg.receipt.json'));
  assert.deepEqual(load(join(directory, 'document.json')), document, 'actual export document differs');
  for (const key of ['svgDigest', 'outputDigest']) assert.equal(receipt[key], sha(actual), `actual bytes ${key}`);
  for (const key of ['inputSvgDigest', 'sceneSvgDigest']) assert.equal(receipt[key], sha(publication), `current input ${key}`);
  assert.equal(receipt.bytes, actual.length); assert.equal(receipt.format, 'svg'); assert.equal(receipt.geometryVerified, true);
  assert.equal(receipt.documentId, document.id); assert.equal(receipt.revision, document.revision);
  assert.equal(receipt.sourceDigest, document.architecture.sourceDigest); assert.equal(receipt.irDigest, document.architecture.irDigest);
  assert.equal(receipt.publicationOrigin, join(root, 'src/archcanvas_publication/exporter.py')); read(String(receipt.publicationOrigin));
  const sourceFile = safe(String(receipt.path)); assert.ok(sourceFile.startsWith(join(root, '.archcanvas') + '/'));
  assert.equal(sourceFile.split('/').at(-2), expectedUuid); assert.equal(sourceFile.split('/').at(-1), 'figure.svg');
  for (const name of ['figure.svg', 'figure.svg.receipt.json', 'document.json'])
    assert.deepEqual(read(join(dirname(sourceFile), name)), read(join(directory, name)), `actual live exporter source ${name}`);
  const text = actual.toString(), size = dimensions(scene, text); assert.deepEqual(receipt.viewBox, size.viewBox);
  assert.equal(receipt.widthMm, size.widthMm); assert.ok(Math.abs(Number(receipt.heightMm) - size.heightMm) <= 1e-10);
  const expectedTree = parseXml(publication), actualTree = parseXml(text);
  // Independent physical formula first; publisher and renderer serialize root
  // millimetres at five versus two decimals. Only those two root strings differ.
  dimensions(scene, publication); actualTree.attributes.width = expectedTree.attributes.width; actualTree.attributes.height = expectedTree.attributes.height;
  assert.deepEqual(canonicalTree(actualTree), canonicalTree(expectedTree), 'complete publication XML except checked root mm serialization');
  assertSvgStyles(document, scene, text); assertLegend(document, scene, text); assertEndpoints(scene);
  return { uuid: expectedUuid, receiptPath: relative(root, sourceFile), dimensions: size, fonts: receipt.fonts,
    completeXmlException: 'Only independently checked root width/height mm formatting; metadata/text/paths/objects remain equal.' };
}
function detailCoverage(document: CanvasDocument, scene: Scene, nodeId: string) {
  const scope = scene.exportScope; assert.ok(scope); assert.equal(scope.selectedNodeId, nodeId);
  const internal = scope.internalEdgeIds, boundary = scope.boundaryEdges.map(edge => edge.edgeId), omitted = scope.omittedEdgeIds;
  const all = [...internal, ...boundary, ...omitted]; assert.equal(new Set(all).size, all.length);
  assert.deepEqual([...all].sort(), document.architecture.edges.map(edge => edge.id).sort(), 'detail canonical partition');
  const visible = scene.edges.flatMap(edge => edge.canonicalEdgeIds);
  assert.deepEqual([...visible, ...scene.hiddenEdges].sort(), [...internal, ...boundary].sort(), 'detail visible/hidden membership');
  for (const item of scope.boundaryEdges) {
    const canonical = document.architecture.edges.find(edge => edge.id === item.edgeId)!;
    for (const key of ['source', 'target', 'tensorId', 'role'] as const) assert.deepEqual(item[key], canonical[key]);
    const edge = scene.edges.find(edge => edge.canonicalEdgeIds.includes(item.edgeId)); assert.ok(edge); assert.deepEqual(edge.canonicalEdgeIds, [item.edgeId]);
  }
}
function caseAudit(item: PlanCase) {
  assert.ok(/^[a-z0-9-]+$/.test(item.caseId)); assert.ok(item.widthMm === 85 || item.widthMm === 180);
  const directory = join(plan.browserDirectory, item.caseId), core = join(plan.coreDirectory, item.caseId);
  const document = load<CanvasDocument>(join(directory, 'document.json')), envelope = load<{ document: CanvasDocument; revision: number }>(join(directory, 'saved-envelope.json'));
  assert.deepEqual(envelope.document, document); assert.ok(Number.isSafeInteger(envelope.revision) && envelope.revision > 0);
  const stored = load<{ document: CanvasDocument; revision: number }>(join(plan.documentStoreDirectory, document.id + '.json'));
  // The current store can advance during a later style case. Saved envelopes
  // retain the actual version; current store agreement is required when the
  // same storage revision is still present, never inferred for old cases.
  if (stored.revision === envelope.revision) assert.deepEqual(stored, envelope, 'current actual saved store');
  assert.deepEqual(document.pageSpec, { widthMm: item.widthMm, background: '#ffffff', preset: item.preset });
  const basePrefix = item.baselineKind === 'cnn12' ? join(here, 'baseline/cnn12', item.baselineCaseId) : join(here, 'baseline/historical-transformer', item.baselineCaseId);
  const baseDocument = load<CanvasDocument>(item.baselineKind === 'cnn12' ? join(basePrefix, 'browser-after-union/document.json') : basePrefix + '.canvas.json');
  const baselineScene = load<Scene>(item.baselineKind === 'cnn12' ? join(basePrefix, 'core-after-union/scene.json') : basePrefix + '.scene.json');
  const expected = serial(baseDocument); expected.revision = document.revision; expected.pageSpec = serial(document.pageSpec);
  if (item.edgeStyleOverrides) {
    assert.ok(Object.keys(item.edgeStyleOverrides).every(id => baseDocument.architecture.edges.some(edge => edge.id === id)));
    expected.edgeStyleOverrides = { ...expected.edgeStyleOverrides, ...serial(item.edgeStyleOverrides) };
  }
  const replayCase = replay?.cases.find(result => result.caseId === item.caseId);
  if (replay) {
    assert.ok(replayCase); assert.equal(replayCase.completeDocumentExact, true);
    assert.equal(safe(replayCase.actualDocumentPath), safe(join(directory, 'document.json')));
    assert.deepEqual(document, load<CanvasDocument>(replayCase.expectedDocument.path), 'complete Canvas frozen native-operation journal');
    assert.deepEqual(document.architecture, baseDocument.architecture, 'native journal changed model source/facts');
  } else assert.deepEqual(document, expected, 'complete Canvas baseline with only declared page/revision/override scope');
  const scene = load<Scene>(join(core, 'scene.json')), exported = load<Scene>(join(core, 'export.scene.json'));
  assertCoverage(document, scene); assertStyles(document, scene); assertEndpoints(scene);
  const publication = read(join(core, 'publication.svg')).toString(), interactive = read(join(core, 'interactive.svg')).toString();
  if (!item.edgeStyleOverrides) {
    const before = item.geometryReference === 'frozen-journal' ? load<Scene>(replayCase!.expectedScene.path) : serial(baselineScene);
    if (item.geometryReference === 'frozen-journal') assert.ok(replayCase, 'frozen history geometry requires completed independent replay');
    before.revision = scene.revision;
    assertProtectedScene(before, scene, item.geometryReference !== 'frozen-journal' && item.preset === 'monochrome' && baseDocument.pageSpec.preset === 'paper');
  } else {
    assert.deepEqual(scene.sourceFacts, baselineScene.sourceFacts, 'override changed facts');
    const stripPorts = (node: Scene['nodes'][number]) => { const { ports: _, fill: __, stroke: ___, ...rest } = node; return rest; };
    assert.deepEqual(scene.nodes.map(stripPorts), baselineScene.nodes.map(stripPorts), 'override changed manual node geometry');
  }
  if (item.scope.kind === 'document') assert.deepEqual(exported, scene, 'whole current export scene differs');
  else detailCoverage(document, exported, item.scope.nodeId);
  // Whole-style coverage assertion is not used for detail omitted edges.
  assertSvgStyles(document, scene, interactive); assertLegend(document, scene, interactive);
  assertSvgStyles(document, exported, publication); assertLegend(document, exported, publication);
  const imageResults = item.views.map(view => {
    assert.ok(/^[a-z0-9-]+$/.test(view));
    const before = load<Record<string, unknown>>(join(directory, view + '-before.json')), after = load<Record<string, unknown>>(join(directory, view + '-after.json'));
    for (const observation of [before, after]) {
      const dataset = observation.dataset as Record<string, string>;
      assert.equal(dataset.sceneKind, 'committed'); assert.equal(dataset.committedRevision, String(document.revision));
      assert.deepEqual(JSON.parse(dataset.expandedIds), document.expandedIds); assert.deepEqual(JSON.parse(dataset.pinnedIds), document.pinnedObjects);
      const svg = String(observation.svg); assert.deepEqual(canonicalTree(parseXml(svg)), canonicalTree(parseXml(interactive)), 'complete current interactive XML');
      assertSvgStyles(document, scene, svg); assertLegend(document, scene, svg); dimensions(scene, svg);
      const meta = JSON.parse(flatten(parseXml(svg)).find(node => node.name === 'metadata')!.text), publicMeta = observation.metadata as Record<string, unknown>;
      const withoutHeight = ({ heightMm: _, ...rest }: Record<string, unknown>) => rest;
      assert.deepEqual(withoutHeight(publicMeta), withoutHeight(meta)); assert.deepEqual(Object.keys(publicMeta).sort(), Object.keys(meta).sort());
      const delta = Math.abs(Number(publicMeta.heightMm) - Number(meta.heightMm)); assert.ok(delta <= 1e-10);
      if (delta) numberExceptions.push({ caseId: item.caseId, view, differenceMm: delta, limitMm: 1e-10, scope: 'Observation JSON heightMm only; SVG not changed.' });
      const urls = [...observation.scripts as string[], ...observation.styles as string[]].map(url => new URL(url).pathname);
      assert.deepEqual(urls, ['/assets/' + plan.build.js.path.split('/').at(-1), '/assets/' + plan.build.css.path.split('/').at(-1)]);
      for (const url of [...observation.scripts as string[], ...observation.styles as string[]])
        assert.equal(new URL(url).origin, new URL(String(observation.url)).origin, 'assets must come from the actual observed page origin');
      assert.match(String(observation.camera), /^matrix\([-\d.eE+, ]+\)$/);
      assert.equal(publicMeta.revision, document.revision);
    }
    for (const key of ['dataset', 'svg', 'camera', 'metadata', 'scripts', 'styles', 'url', 'viewport']) assert.deepEqual(before[key], after[key], `screenshot state changed ${key}`);
    const jpeg = read(join(directory, view + '.jpg')); assert.ok(jpeg[0] === 0xff && jpeg[1] === 0xd8, 'not an actual JPEG original');
    return { view, exactObservationState: true, screenshot: relative(root, safe(join(directory, view + '.jpg'))), pixelsReviewed: false };
  });
  const binding = load<{ capturedAt: string; links: { href: string; text: string }[] }>(join(directory, 'export-binding.json'));
  assert.ok(Number.isFinite(Date.parse(binding.capturedAt)));
  assert.equal(binding.links.length, 3);
  const svgLinks = binding.links.filter(link => /^\/api\/exports\/[0-9a-f]{32}\/figure\.svg$/.test(link.href));
  assert.equal(svgLinks.length, 2); assert.equal(svgLinks[0].href, svgLinks[1].href);
  const uuid = svgLinks[0].href.match(/^\/api\/exports\/([0-9a-f]{32})\/figure\.svg$/)![1];
  assert.equal(binding.links.filter(link => link.href === `/api/exports/${uuid}/receipt`).length, 1);
  const copies = load<{ actualUiBinding?: unknown; actualExportUiBindings?: string[]; serverArtifactsCopiedUnmodified?: boolean;
    records: { source: string; copy: string; bytes: number; sha256: string }[]; modelsExecuted: boolean }>(join(directory, 'artifact-copy-receipt.json'));
  const uuidByName = new Map([['document.json', uuid], ['figure.svg', uuid], ['figure.svg.receipt.json', uuid]]);
  const additionalArtifacts: unknown[] = [];
  if (copies.actualUiBinding !== undefined) assert.deepEqual(copies.actualUiBinding, binding);
  else {
    assert.deepEqual(copies.actualExportUiBindings, ['export-binding.json', 'pdf-export-binding.json']);
    assert.equal(copies.serverArtifactsCopiedUnmodified, true);
    const pdfBinding = load<{ capturedAt: string; links: { href: string; text: string }[] }>(join(directory, 'pdf-export-binding.json'));
    assert.ok(Number.isFinite(Date.parse(pdfBinding.capturedAt))); assert.equal(pdfBinding.links.length, 3);
    const pdfLinks = pdfBinding.links.filter(link => /^\/api\/exports\/[0-9a-f]{32}\/figure\.pdf$/.test(link.href));
    assert.equal(pdfLinks.length, 2); assert.equal(pdfLinks[0].href, pdfLinks[1].href);
    const pdfUuid = pdfLinks[0].href.match(/^\/api\/exports\/([0-9a-f]{32})\/figure\.pdf$/)![1];
    assert.equal(pdfBinding.links.filter(link => link.href === `/api/exports/${pdfUuid}/receipt`).length, 1);
    uuidByName.set('figure.pdf', pdfUuid); uuidByName.set('figure.pdf.receipt.json', pdfUuid);
    const pdf = read(join(directory, 'figure.pdf')), pdfReceipt = load<Record<string, unknown>>(join(directory, 'figure.pdf.receipt.json'));
    assert.equal(pdf.subarray(0, 5).toString(), '%PDF-'); assert.equal(pdfReceipt.format, 'pdf');
    assert.equal(pdfReceipt.bytes, pdf.length); assert.equal(pdfReceipt.outputDigest, sha(pdf));
    assert.equal(pdfReceipt.inputSvgDigest, sha(publication)); assert.equal(pdfReceipt.sceneSvgDigest, sha(publication));
    assert.equal(pdfReceipt.documentId, document.id); assert.equal(pdfReceipt.revision, document.revision);
    assert.equal(pdfReceipt.sourceDigest, document.architecture.sourceDigest); assert.equal(pdfReceipt.irDigest, document.architecture.irDigest);
    assert.equal(pdfReceipt.widthMm, exported.pageSpec.widthMm);
    assert.ok(Math.abs(Number(pdfReceipt.heightMm) - exported.pageSpec.widthMm * exported.bounds.height / exported.bounds.width) <= 1e-10);
    assert.equal(pdfReceipt.publicationOrigin, join(root, 'src/archcanvas_publication/exporter.py'));
    const sourcePdf = safe(String(pdfReceipt.path)); assert.equal(sourcePdf.split('/').at(-2), pdfUuid);
    assert.deepEqual(load(join(dirname(sourcePdf), 'document.json')), document, 'actual PDF source document');
    additionalArtifacts.push({ format: 'pdf', uuid: pdfUuid, outputDigest: sha(pdf), actualInputSceneSvgExact: true,
      authenticityOnly: true, pixelOrPhysicalAcceptance: false });
  }
  assert.equal(copies.modelsExecuted, false);
  for (const row of copies.records) {
    const copy = read(row.copy); assert.equal(copy.length, row.bytes); assert.equal(sha(copy), row.sha256);
    assert.equal(dirname(safe(row.copy)), safe(directory));
    // The mutable document store may advance. Each original saved envelope is
    // still byte-bound by its copy receipt; immutable export outputs stay exact.
    if (row.source.includes('/exports/')) {
      assert.equal(row.source.split('/').at(-2), uuidByName.get(row.copy.split('/').at(-1)!));
      assert.deepEqual(read(row.source), copy, 'immutable actual export source/copy bytes');
    } else {
      assert.equal(safe(row.source), safe(join(plan.documentStoreDirectory, document.id + '.json')));
      assert.equal(row.copy.split('/').at(-1), 'saved-envelope.json');
      if (stored.revision === envelope.revision) assert.deepEqual(read(row.source), copy, 'current stored envelope source/copy bytes');
    }
  }
  const copiedNames = copies.records.map(row => row.copy.split('/').at(-1));
  for (const name of ['document.json', 'figure.svg', 'figure.svg.receipt.json', 'saved-envelope.json'])
    assert.equal(copiedNames.filter(item => item === name).length, 1, `actual copy receipt missing/duplicated ${name}`);
  const exportResult = actualExport(directory, document, exported, publication, uuid);
  return { caseId: item.caseId, baselineCaseId: item.baselineCaseId, preset: item.preset, widthMm: item.widthMm,
    sourceFactsExact: true, canonicalCoverageExact: true, unchangedRouteBaselineChecked: !item.edgeStyleOverrides,
    completeCanvasExpectedSource: replayCase ? 'Frozen historical document contract replay of declared native action chain' : 'Matched raw baseline with declared page/revision/override changes',
    geometryReference: item.geometryReference ?? 'matched-baseline',
    historyBaselineNodeDeltas: item.geometryReference === 'frozen-journal' ? scene.nodes.flatMap(node => {
      const old = baselineScene.nodes.find(old => old.id === node.id); return old && ['x', 'y', 'width', 'height'].some(key => node[key as keyof typeof node] !== old[key as keyof typeof old])
        ? [{ id: node.id, before: { x: old.x, y: old.y, width: old.width, height: old.height }, current: { x: node.x, y: node.y, width: node.width, height: node.height } }] : [];
    }) : [],
    boundedOverrideGeometryException: item.edgeStyleOverrides ?? null, roleStylesAndTruthfulLegend: true,
    views: imageResults, actualExport: exportResult, additionalArtifacts, storageRevision: envelope.revision, documentRevision: document.revision };
}
let error: unknown;
try { for (const item of plan.cases) results.push(caseAudit(item)); }
catch (failure) { error = { name: failure instanceof Error ? failure.name : 'Error', message: String(failure), stack: failure instanceof Error ? failure.stack : null }; }
const before = [...inputs.values()].sort((a, b) => a.path.localeCompare(b.path));
const after = before.map(binding => { const bytes = readFileSync(safe(binding.path)); return { path: binding.path, bytes: bytes.length, sha256: sha(bytes) }; });
const exact = JSON.stringify(before) === JSON.stringify(after);
const report = { protocol: 'archcanvas-monochrome-role-independent-browser-readback/1', finishedAt: new Date().toISOString(),
  status: error || !exact ? 'failed' : 'bounded-pass', plannedCases: plan.cases.length, completedCases: results.length,
  cases: results, error: error ?? null, checks, inputsBefore: before, inputsAfter: after, inputBytesUnchanged: exact,
  heightMmJsonRoundtripExceptions: numberExceptions, expectedFromProduct: false, userModelsExecuted: false, dependenciesInstalled: false,
  humans: 0, physicalPublicationCertified: false, pixelsReviewedByThisScript: false,
  limits: 'Bounded canonical/style/geometry/artifact consistency. AI pixels, native history chain, publication/fonts/hardware, performance and human tasks need their separate evidence.' };
write('report.json', report); console.log(JSON.stringify({ status: report.status, completedCases: results.length, plannedCases: plan.cases.length,
  inputBytesUnchanged: exact, report: relative(root, join(out, 'report.json')), error: error ?? null }));
if (error || !exact) process.exitCode = 1;
