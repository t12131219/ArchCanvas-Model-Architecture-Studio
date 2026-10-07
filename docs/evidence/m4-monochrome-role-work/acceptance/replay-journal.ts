// Expected document transitions come from the pre-change immutable document
// contract, not current product operations or current renderer observations.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { CanvasDocument, HistoryAction } from '../../../../studio/src/core/types.ts';
import { createHistory, reduceHistory, validateDocument, buildScene as frozenContractScene } from './baseline/provenance/studio/src/core/index.ts';

const here = dirname(fileURLToPath(import.meta.url)), root = resolve(here, '../../../..');
const [journalArg, outputArg] = process.argv.slice(2); assert.ok(journalArg && outputArg && process.argv.length === 4);
const safe = (path: string) => { const full = resolve(root, path); assert.ok(full.startsWith(root + '/')); return full; };
const output = safe(outputArg); mkdirSync(output);
type Binding = { path: string; bytes: number; sha256: string };
type Checkpoint = { caseId: string; documentPath: string; expectedRevision: number };
type Step = { action: HistoryAction; expectedRevision: number; checkpoints?: Checkpoint[] } |
  { reloadEnvelopePath: string; expectedRevision: number; checkpoints?: Checkpoint[] };
type Journal = { protocol: 'archcanvas-monochrome-role-native-operation-journal/1';
  sessions: { id: string; initialEnvelopePath: string; steps: Step[] }[] };
const inputs = new Map<string, Binding>();
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
function read(path: string) {
  const full = safe(path), bytes = readFileSync(full), row = { path: relative(root, full), bytes: bytes.length, sha256: sha(bytes) };
  if (inputs.has(row.path)) assert.deepEqual(row, inputs.get(row.path), 'journal input changed'); else inputs.set(row.path, row); return bytes;
}
const load = <T>(path: string): T => JSON.parse(read(path).toString());
const capture = load<{ records: { source: Binding; copy: Binding }[] }>(join(here, 'baseline/capture.json'));
for (const row of capture.records.filter(row => row.source.path.startsWith('studio/src/core/'))) {
  read(row.copy.path); assert.deepEqual(inputs.get(row.copy.path), row.copy, 'frozen historical executor source');
}
const journal = load<Journal>(journalArg); assert.equal(journal.protocol, 'archcanvas-monochrome-role-native-operation-journal/1');
read(fileURLToPath(import.meta.url));
const seen = new Set<string>(), cases: unknown[] = [], transitions: unknown[] = [];
let error: unknown;
try {
  for (const session of journal.sessions) {
    assert.ok(/^[a-z0-9-]+$/.test(session.id));
    const initial = load<{ document: CanvasDocument; revision: number }>(session.initialEnvelopePath);
    validateDocument(initial.document); let history = createHistory(initial.document);
    // Every browser seed is a declared exact historical document, not a fresh
    // silently normalized product expectation. Reload sessions may start from
    // an already verified native checkpoint below.
    const seedReceiptPath = join(here, '../seed-session-attempt-1/receipt.json');
    const seedReceipt = load<{ records: { baseline: string; baselineSha: string; envelope: string; bytes: number; sha256: string }[] }>(seedReceiptPath);
    const seedRow = seedReceipt.records.find(row => dirname(row.envelope) && row.envelope.split('/').at(-1) === session.initialEnvelopePath.split('/').at(-1));
    if (session.initialEnvelopePath.includes('/seed-session-attempt-1/')) {
      assert.ok(seedRow, 'initial seed not bound by actual seed receipt');
      const baseline = read(seedRow.baseline); assert.equal(sha(baseline), seedRow.baselineSha);
      assert.deepEqual(initial.document, JSON.parse(baseline.toString()), 'seed document differs from exact frozen baseline');
      const raw = read(session.initialEnvelopePath); assert.equal(raw.length, seedRow.bytes); assert.equal(sha(raw), seedRow.sha256);
    }
    const source = JSON.stringify(initial.document.architecture), binding = initial.document.sourceBindingDigest;
    for (const [index, step] of session.steps.entries()) {
      const before = history.document.revision;
      if ('reloadEnvelopePath' in step) {
        const reopened = load<{ document: CanvasDocument; revision: number }>(step.reloadEnvelopePath);
        assert.deepEqual(reopened.document, history.document, 'native reload input differs from preceding frozen-contract expected document');
        history = createHistory(reopened.document);
      } else {
        assert.ok(['apply', 'undo', 'redo'].includes(step.action.type));
        if (step.action.type === 'apply') assert.ok(step.action.operations.every(operation => ['page', 'expand', 'edgeStyle'].includes(operation.type)), 'journal permits only declared browser workflow operations');
        history = reduceHistory(history, step.action);
      }
      assert.equal(history.document.revision, step.expectedRevision, `native action batch/revision ${session.id}/${index}`);
      assert.equal(JSON.stringify(history.document.architecture), source, 'operation journal changed canonical architecture');
      assert.equal(history.document.sourceBindingDigest, binding);
      const checkpointResults = [];
      for (const checkpoint of step.checkpoints ?? []) {
        assert.ok(/^[a-z0-9-]+$/.test(checkpoint.caseId)); assert.ok(!seen.has(checkpoint.caseId)); seen.add(checkpoint.caseId);
        assert.equal(checkpoint.expectedRevision, history.document.revision);
        const actual = load<CanvasDocument>(checkpoint.documentPath);
        assert.deepEqual(actual, history.document, `complete expected Canvas journal ${checkpoint.caseId}`);
        const target = join(output, checkpoint.caseId); mkdirSync(target);
        writeFileSync(join(target, 'expected-document.json'), JSON.stringify(history.document, null, 2) + '\n', { flag: 'wx' });
        writeFileSync(join(target, 'expected-scene.json'), JSON.stringify(frozenContractScene(history.document), null, 2) + '\n', { flag: 'wx' });
        const outputBinding = (name: string) => {
          const bytes = readFileSync(join(target, name)); return { path: relative(root, join(target, name)), bytes: bytes.length, sha256: sha(bytes) };
        };
        const record = { caseId: checkpoint.caseId, sessionId: session.id, step: index, expectedRevision: history.document.revision,
          actualDocumentPath: checkpoint.documentPath, expectedDocumentPath: relative(root, join(target, 'expected-document.json')),
          expectedDocument: outputBinding('expected-document.json'), expectedScene: outputBinding('expected-scene.json'),
          completeDocumentExact: true, pastCount: history.past.length, futureCount: history.future.length };
        cases.push(record); checkpointResults.push(record);
      }
      transitions.push({ sessionId: session.id, step: index, beforeRevision: before, afterRevision: history.document.revision,
        action: step, pastCount: history.past.length, futureCount: history.future.length, checkpoints: checkpointResults });
    }
  }
} catch (failure) { error = { name: failure instanceof Error ? failure.name : 'Error', message: String(failure), stack: failure instanceof Error ? failure.stack : null }; }
const before = [...inputs.values()].sort((a, b) => a.path.localeCompare(b.path));
const after = before.map(row => { const bytes = readFileSync(safe(row.path)); return { path: row.path, bytes: bytes.length, sha256: sha(bytes) }; });
const exact = JSON.stringify(before) === JSON.stringify(after);
const receipt = { protocol: 'archcanvas-monochrome-role-frozen-contract-journal-replay/1', finishedAt: new Date().toISOString(),
  status: error || !exact ? 'failed' : 'bounded-pass', journalPath: relative(root, safe(journalArg)),
  sessions: journal.sessions.length, caseCount: cases.length, cases, transitions, error: error ?? null,
  inputsBefore: before, inputsAfter: after, inputBytesUnchanged: exact,
  independentExpectedExecutor: 'Pre-change frozen historical document and core modules; all source bytes match immutable baseline capture.',
  currentProductCalledToDeriveExpected: false, modelsExecuted: false, dependenciesInstalled: false,
  limits: 'Exact document transitions for the recorded native operations only. Journal honesty relies on separately bound actual UI observations; no screenshot/pixel or physical/human/performance acceptance.' };
writeFileSync(join(output, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ status: receipt.status, caseCount: cases.length, inputBytesUnchanged: exact, error: error ?? null,
  receipt: relative(root, join(output, 'receipt.json')) }));
if (error || !exact) process.exitCode = 1;
