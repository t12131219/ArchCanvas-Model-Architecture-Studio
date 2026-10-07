import { studioTelemetry } from './perf';
import type { FrameSample, PerfSnapshot } from './perf';

type SceneStats = { nodeCount: number; edgeCount: number; expandableCount: number; canonicalVisibleNodeIds: string[] };
export type StudioBenchmarkResult = {
  schemaVersion: 1;
  scenario: 'non-root-expand-collapse-fit';
  measurement: { latency: 'two-animation-frame-paint-proxy'; eventTiming: 'observed-separately'; syntheticScenarioEvents: true; sampleCount: number; warmupCount: number };
  environment: { userAgent: string; viewport: { width: number; height: number; devicePixelRatio: number }; url: string; visibility: PerfSnapshot['visibility'] };
  binding: { documentId: string; revisionBefore: number; revisionAfter: number; sourceDigest: string; irDigest: string };
  target: { canonicalNodeId: string; label: string; depth: number };
  scene: { before: SceneStats; expanded: SceneStats; after: SceneStats };
  idleFrameBaseline: { frames: FrameSample; visibility: PerfSnapshot['visibility'] };
  trials: { iteration: number; operation: 'expand' | 'collapse'; durationMs: number; handlerDurationMs: number; beforeNodeCount: number; afterNodeCount: number }[];
  summary: { expandPaintProxyP50Ms: number | null; expandPaintProxyP95Ms: number | null; collapsePaintProxyP95Ms: number | null; expandHandlerP95Ms: number | null; collapseHandlerP95Ms: number | null; maxLongTaskMs: number | null; fps: number; intervalsOver50Ms: number; p95FrameMs: number; maxFrameMs: number };
  snapshot: PerfSnapshot;
};

type BenchmarkOptions = { frameMs?: number; waitMs?: number; sampleCount?: number; onProgress?: (completed: number, total: number) => void };

function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * p) - 1))];
}

async function waitFor(predicate: () => boolean, timeoutMs: number): Promise<boolean> {
  const started = performance.now();
  while (performance.now() - started < timeoutMs) {
    if (predicate()) return true;
    await new Promise(resolve => setTimeout(resolve, 12));
  }
  return predicate();
}

function sceneStats(): SceneStats {
  const nodes = new Set([...document.querySelectorAll('.publication-scene [data-node-id]')].map(node => node.getAttribute('data-node-id')!));
  const edges = new Set([...document.querySelectorAll('.publication-scene [data-edge-id]')].map(edge => edge.getAttribute('data-edge-id')!));
  return { nodeCount: nodes.size, edgeCount: edges.size, expandableCount: document.querySelectorAll('.publication-scene [data-expand-id]').length, canonicalVisibleNodeIds: [...nodes].sort() };
}

function treeToggle(id: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll<HTMLElement>('[data-tree-node-id]')].find(node => node.dataset.treeNodeId === id)?.querySelector<HTMLButtonElement>(':scope > .tree-row > .tree-toggle') ?? undefined;
}

function sceneBinding() {
  const svg = document.querySelector('.publication-scene > svg');
  if (!svg) throw new Error('当前画布还没有 SVG。');
  const metadata = JSON.parse(svg.querySelector('metadata')?.textContent ?? '{}') as { sourceDigest?: string; irDigest?: string };
  return { documentId: svg.getAttribute('data-document-id') ?? '', revision: Number(svg.getAttribute('data-revision')), sourceDigest: metadata.sourceDigest ?? '', irDigest: metadata.irDigest ?? '' };
}

/**
 * A repeated browser scenario behind an explicit benchmark UI. It uses the
 * shipped tree controls to exercise React + SVG, and names its two-frame paint
 * boundary honestly: synthetic scenario clicks are not browser Event Timing.
 */
export async function runStudioBenchmark(options: BenchmarkOptions = {}): Promise<StudioBenchmarkResult> {
  const frameMs = options.frameMs ?? 2000;
  const waitMs = options.waitMs ?? 2000;
  const sampleCount = Math.round(Math.max(20, Math.min(100, options.sampleCount ?? 20)));
  const candidate = [...document.querySelectorAll<HTMLElement>('[data-tree-node-id]')].find(node => {
    const toggle = node.querySelector<HTMLButtonElement>(':scope > .tree-row > .tree-toggle');
    return Number(node.dataset.treeDepth) > 0 && node.getAttribute('aria-expanded') === 'false' && toggle && !toggle.disabled;
  });
  if (!candidate) throw new Error('展开一个根模块，并保留至少一个收起的子容器，再运行性能采样。');
  const target = { canonicalNodeId: candidate.dataset.treeNodeId!, label: candidate.querySelector('.tree-label > span:nth-child(2)')?.textContent ?? '', depth: Number(candidate.dataset.treeDepth) };
  const before = sceneStats();
  const bindingBefore = sceneBinding();
  studioTelemetry.reset();
  const idleFrames = await studioTelemetry.sampleFrames(frameMs);
  const idleFrameBaseline = { frames: idleFrames, visibility: studioTelemetry.snapshot().visibility };
  const trials: StudioBenchmarkResult['trials'] = [];
  let expanded = before;
  const runToggle = async (operation: 'expand' | 'collapse', iteration: number, record: boolean) => {
    const button = treeToggle(target.canonicalNodeId);
    if (!button || button.disabled) throw new Error('性能采样目标已不可见。');
    const beforeCount = sceneStats().nodeCount;
    const previousId = studioTelemetry.snapshot().interactions.at(-1)?.id;
    button.click();
    if (!await waitFor(() => studioTelemetry.snapshot().interactions.at(-1)?.id !== previousId, waitMs)) throw new Error(`性能采样 ${operation} 未得到两帧测量。`);
    const sample = studioTelemetry.snapshot().interactions.at(-1)!;
    if (sample.name !== `visual:${operation}` || sample.durationMs === null) throw new Error('展开/收起测量与实际操作不一致。');
    const after = sceneStats();
    if (operation === 'expand') expanded = after;
    if (record) trials.push({ iteration, operation, durationMs: sample.durationMs, handlerDurationMs: sample.handlerDurationMs ?? 0, beforeNodeCount: beforeCount, afterNodeCount: after.nodeCount });
  };
  // Warm the same frontier before timing; restore it before starting trials.
  await runToggle('expand', 0, false);
  await runToggle('collapse', 0, false);
  studioTelemetry.reset();
  const frames = studioTelemetry.sampleFrames(frameMs);
  for (let iteration = 1; iteration <= sampleCount; iteration++) {
    await runToggle('expand', iteration, true);
    await runToggle('collapse', iteration, true);
    options.onProgress?.(iteration, sampleCount);
  }
  const fit = document.querySelector<HTMLButtonElement>('button[title^="适合画布"]');
  if (!fit) throw new Error('性能采样缺少适合画布按钮。');
  const previousId = studioTelemetry.snapshot().interactions.at(-1)?.id;
  fit.click();
  if (!await waitFor(() => studioTelemetry.snapshot().interactions.at(-1)?.id !== previousId, waitMs)) throw new Error('适合画布没有得到两帧测量。');
  const frame = await frames;
  const snapshot = studioTelemetry.snapshot();
  const bindingAfter = sceneBinding();
  if (bindingAfter.documentId !== bindingBefore.documentId || bindingAfter.sourceDigest !== bindingBefore.sourceDigest || bindingAfter.irDigest !== bindingBefore.irDigest) throw new Error('性能采样期间已切换源码绑定，请重新采样。');
  return {
    schemaVersion: 1,
    scenario: 'non-root-expand-collapse-fit',
    measurement: { latency: 'two-animation-frame-paint-proxy', eventTiming: 'observed-separately', syntheticScenarioEvents: true, sampleCount, warmupCount: 1 },
    environment: { userAgent: navigator.userAgent, viewport: { width: innerWidth, height: innerHeight, devicePixelRatio: devicePixelRatio || 1 }, url: location.href, visibility: snapshot.visibility },
    binding: { documentId: bindingBefore.documentId, revisionBefore: bindingBefore.revision, revisionAfter: bindingAfter.revision, sourceDigest: bindingBefore.sourceDigest, irDigest: bindingBefore.irDigest },
    target,
    scene: { before, expanded, after: sceneStats() },
    idleFrameBaseline,
    trials,
    summary: {
      expandPaintProxyP50Ms: percentile(trials.filter(trial => trial.operation === 'expand').map(trial => trial.durationMs), .5),
      expandPaintProxyP95Ms: percentile(trials.filter(trial => trial.operation === 'expand').map(trial => trial.durationMs), .95),
      collapsePaintProxyP95Ms: percentile(trials.filter(trial => trial.operation === 'collapse').map(trial => trial.durationMs), .95),
      expandHandlerP95Ms: percentile(trials.filter(trial => trial.operation === 'expand').map(trial => trial.handlerDurationMs), .95),
      collapseHandlerP95Ms: percentile(trials.filter(trial => trial.operation === 'collapse').map(trial => trial.handlerDurationMs), .95),
      maxLongTaskMs: snapshot.supported.longTasks ? snapshot.longTasks.reduce((max, task) => Math.max(max, task.durationMs), 0) : null,
      fps: frame.fps,
      intervalsOver50Ms: frame.droppedFrames,
      p95FrameMs: frame.p95FrameMs,
      maxFrameMs: frame.maxFrameMs,
    },
    snapshot,
  };
}

declare global { interface Window { __ARCHCANVAS_BENCHMARK__?: (options?: BenchmarkOptions) => Promise<StudioBenchmarkResult> } }
if (typeof window !== 'undefined') window.__ARCHCANVAS_BENCHMARK__ = runStudioBenchmark;
