import test from 'node:test';
import assert from 'node:assert/strict';
const { validateStudioPerformance } = await import(new URL('../../scripts/validate_studio_performance.mjs', import.meta.url).href);

// A deliberately synthetic oracle only for the receipt verifier; never saved
// as performance evidence and never used to certify a browser latency.
function receipt() {
  const scene = (ids: string[]) => ({ canonicalVisibleNodeIds: ids, nodeCount: ids.length, edgeCount: 1, expandableCount: 1 });
  const trials = Array.from({ length: 20 }, (_, index) => [
    { iteration: index + 1, operation: 'expand', durationMs: index + 1, handlerDurationMs: 1, beforeNodeCount: 2, afterNodeCount: 3 },
    { iteration: index + 1, operation: 'collapse', durationMs: index + 2, handlerDurationMs: 2, beforeNodeCount: 3, afterNodeCount: 2 },
  ]).flat();
  return {
    schemaVersion: 1, scenario: 'non-root-expand-collapse-fit',
    measurement: { latency: 'two-animation-frame-paint-proxy', eventTiming: 'observed-separately', sampleCount: 20, warmupCount: 1, syntheticScenarioEvents: true },
    environment: { viewport: { width: 1000, height: 800, devicePixelRatio: 1 } },
    binding: { documentId: 'oracle', sourceDigest: 'source', irDigest: 'ir', revisionBefore: 1, revisionAfter: 43 },
    target: { canonicalNodeId: 'block', depth: 1, label: 'block' },
    scene: { before: scene(['root', 'block']), expanded: scene(['root', 'block', 'child']), after: scene(['root', 'block']) },
    trials,
    idleFrameBaseline: { frames: { requestedMs: 2000, fps: 60, p95FrameMs: 17, maxFrameMs: 18 } },
    summary: { expandPaintProxyP50Ms: 10, expandPaintProxyP95Ms: 19, collapsePaintProxyP95Ms: 20, expandHandlerP95Ms: 1, collapseHandlerP95Ms: 2, fps: 60, intervalsOver50Ms: 0, p95FrameMs: 17, maxFrameMs: 18, maxLongTaskMs: null },
    snapshot: { interactions: ['visual:expand', 'visual:collapse', 'fit-canvas'].map(name => ({ name, durationMs: 10 })), eventTiming: [], longTasks: [], supported: { longTasks: false }, frameSamples: [{ requestedMs: 2000, fps: 60, droppedFrames: 0, p95FrameMs: 17, maxFrameMs: 18 }] },
  };
}

function validate(value: unknown) {
  return JSON.stringify(validateStudioPerformance(value));
}

test('receipt verifier recomputes percentiles and rejects unchanged or root frontiers', () => {
  const valid = receipt();
  assert.match(validate(valid), /"status":"validated"/);
  const forged = structuredClone(valid); forged.summary.expandPaintProxyP95Ms = 1;
  assert.throws(() => validate(forged), /percentiles disagree/);
  const handler = structuredClone(valid); handler.summary.expandHandlerP95Ms = 0;
  assert.throws(() => validate(handler), /Handler percentiles disagree/);
  const idle = structuredClone(valid); idle.idleFrameBaseline.frames.requestedMs = 20;
  assert.throws(() => validate(idle), /Invalid idle frame/);
  const unchanged = structuredClone(valid); unchanged.trials[0].afterNodeCount = 2;
  assert.throws(() => validate(unchanged), /Expansion did not add/);
  const root = structuredClone(valid); root.target.depth = 0;
  assert.throws(() => validate(root), /root target/);
});
