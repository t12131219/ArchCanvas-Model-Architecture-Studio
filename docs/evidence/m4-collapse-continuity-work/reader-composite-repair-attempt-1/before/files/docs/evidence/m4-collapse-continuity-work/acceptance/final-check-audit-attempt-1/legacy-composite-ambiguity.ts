// Independent hand-authored witness. The old delimiter key can name either a
// tall packed branch or two short parallel branches. Literal expected output
// is (30,262); no product output supplies that expectation.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { applyVisualBatch, validateDocument } from '../../../../../studio/src/core/index.ts';
import type { ArchitectureNode, CanvasDocument } from '../../../../../studio/src/core/types.ts';

const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
  id, label: id, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear',
  ...(parentId ? { parentId } : {}), children, ports: [], parameters: {}, evidence: 'source',
});
const compact = { root: { x: 50, y: 92 }, 'a|b': { x: 30, y: 62 }, a: { x: 330, y: 62 }, b: { x: 630, y: 62 },
  output: { x: 30, y: 262 }, packedChild: { x: 30, y: 562 }, aChild: { x: 30, y: 62 }, bChild: { x: 30, y: 62 } };
const before: CanvasDocument = {
  schemaVersion: 1, id: 'independent-existing-ambiguous-legacy', title: 'Old composite delimiter ambiguity', revision: 4,
  sourceBindingDigest: 'independent-source', architecture: { schemaVersion: 1, id: 'independent-ambiguity', label: 'Old composite delimiter ambiguity',
    sourceDigest: 'independent-source', irDigest: 'independent-ir', entry: 'model:Independent',
    nodes: [node('root', undefined, ['a|b', 'a', 'b', 'output']), node('a|b', 'root', ['packedChild']),
      node('a', 'root', ['aChild']), node('b', 'root', ['bChild']), node('packedChild', 'a|b'), node('aChild', 'a'), node('bChild', 'b'), node('output', 'root')],
    edges: [], sources: [{ path: 'independent.py', content: '# Static witness; never executed.\n', digest: 'independent-file' }], diagnostics: [] },
  displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: {}, legendItems: [], annotations: [],
  pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' }, expandedIds: ['root'], layout: structuredClone(compact), pinnedObjects: [],
  layoutByFrontier: { root: structuredClone(compact), 'a|b|root': { ...structuredClone(compact), output: { x: 30, y: 700 } } },
};
validateDocument(before);
const expected = { x: 30, y: 262 }, source = new URL('../../../../../studio/src/core/document.ts', import.meta.url);
const bytes = readFileSync(source), sourceDigest = createHash('sha256').update(bytes).digest('hex');
const once = applyVisualBatch(before, [{ type: 'expand', id: 'a', expanded: true }]);
const observed = applyVisualBatch(once, [{ type: 'expand', id: 'b', expanded: true }]);
assert.deepEqual(observed.architecture, before.architecture);
const receipt = { kind: 'independent-existing-composite-legacy-ambiguity-witness', modelsExecuted: false,
  expectedFromProduct: false, sourceBytes: bytes.length, sourceDigest, sourceUnchangedAfter: readFileSync(source).equals(bytes),
  oldKey: 'a|b|root', distinctValidSets: [['a|b', 'root'], ['a', 'b', 'root']], expectedOutputPosition: expected,
  observedOutputPosition: observed.layout.output, expectedPassed: observed.layout.output.x === expected.x && observed.layout.output.y === expected.y,
  visibleBranchAssumption: 'Short a/b branches are disjoint from the output column. The only tall packed branch is not expanded. Existing ambiguous legacy cache must not supply another frontier geometry.' };
writeFileSync(new URL('legacy-composite-ambiguity.receipt.json', import.meta.url), JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
writeFileSync(new URL('legacy-composite-ambiguity.input.json', import.meta.url), JSON.stringify(before, null, 2) + '\n', { flag: 'wx' });
writeFileSync(new URL('legacy-composite-ambiguity.observed.json', import.meta.url), JSON.stringify(observed, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify(receipt));
if (!receipt.expectedPassed) process.exitCode = 1;
