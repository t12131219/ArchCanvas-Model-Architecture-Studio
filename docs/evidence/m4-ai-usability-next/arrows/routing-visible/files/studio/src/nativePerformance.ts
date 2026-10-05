import { studioTelemetry } from './perf.ts';
import type { EventTimingSample } from './perf.ts';

export type Point = { x: number; y: number };
export type Anchor = { screen: Point; canvas: Point };
export type NativeScene = {
  documentId: string; revision: number; sourceDigest: string; irDigest: string;
  visibleIds: string[]; expandedIds: string[]; anchors: Record<string, Anchor>; pinnedIds: string[];
};
export type NativeTrial = {
  eventName: 'click' | 'pointerdown'; eventAt: number; capturedAt: number; trusted: boolean;
  targetId: string; operation: 'expand' | 'collapse'; before: NativeScene;
  after: NativeScene | null; error: string | null;
};

function percentile(values: number[]): number | null {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.ceil(sorted.length * .95) - 1] : null;
}
function distance(a: Point, b: Point): number { return Math.hypot(a.x - b.x, a.y - b.y); }

/** Unmatched or below-threshold native entries stay null, never become zero. */
export function joinNativeTrials(trials: NativeTrial[], events: EventTimingSample[]) {
  const used = new Set<number>();
  return trials.map(trial => {
    const candidates = events.map((entry, index) => ({ entry, index })).filter(({ entry, index }) =>
      !used.has(index) && trial.trusted && entry.name === trial.eventName && entry.targetCanonicalNodeId === trial.targetId && entry.interactionId > 0 &&
      Math.abs(entry.startAt - trial.eventAt) <= 8 && entry.processingStart >= entry.startAt &&
      entry.processingEnd >= entry.processingStart && Number.isFinite(entry.durationMs) && entry.durationMs >= 0);
    // Matching by timestamp is deliberately conservative if entries are ambiguous.
    const match = candidates.length === 1 ? candidates[0] : null;
    if (match) used.add(match.index);
    const after = trial.after;
    const bindingValid = !!after && after.documentId === trial.before.documentId &&
      after.sourceDigest === trial.before.sourceDigest && after.irDigest === trial.before.irDigest &&
      after.revision === trial.before.revision + 1;
    const targetChanged = bindingValid && trial.before.expandedIds.includes(trial.targetId) === (trial.operation === 'collapse') &&
      after!.expandedIds.includes(trial.targetId) === (trial.operation === 'expand');
    const beforeAnchor = trial.before.anchors[trial.targetId];
    const afterAnchor = after?.anchors[trial.targetId];
    const pins = trial.before.pinnedIds.map(id => {
      const before = trial.before.anchors[id], next = after?.anchors[id];
      return { id, measured: !!before && !!next, canvasDisplacementPx: before && next ? distance(before.canvas, next.canvas) : null,
        screenDisplacementPx: before && next ? distance(before.screen, next.screen) : null };
    });
    return { ...trial, bindingValid, targetChanged, nativeEventTiming: match?.entry ?? null,
      nativeInputToNextPaintMs: match?.entry.durationMs ?? null,
      anchorScreenDisplacementPx: targetChanged && beforeAnchor && afterAnchor ? distance(beforeAnchor.screen, afterAnchor.screen) : null,
      pins };
  });
}

export function summarizeNativeTrials(trials: ReturnType<typeof joinNativeTrials>) {
  const valid = trials.filter(trial => trial.bindingValid && trial.targetChanged && !trial.error);
  const durations = valid.flatMap(trial => trial.nativeInputToNextPaintMs === null ? [] : [trial.nativeInputToNextPaintMs]);
  const anchors = valid.flatMap(trial => trial.anchorScreenDisplacementPx === null ? [] : [trial.anchorScreenDisplacementPx]);
  const pinValues = valid.flatMap(trial => trial.pins.flatMap(pin => pin.canvasDisplacementPx === null ? [] : [pin.canvasDisplacementPx]));
  return { capturedTrials: trials.length, validSceneTrials: valid.length, matchedNativeTrials: durations.length,
    nativeInputToNextPaintP95Ms: percentile(durations), anchorScreenMaxPx: anchors.length ? Math.max(...anchors) : null,
    measuredPinCount: pinValues.length, pinCanvasMaxPx: pinValues.length ? Math.max(...pinValues) : null,
    unmeasuredPinCount: valid.reduce((sum, trial) => sum + trial.pins.filter(pin => !pin.measured).length, 0),
    certification: 'pending-fixed-environment-and-review' as const };
}

function readScene(): NativeScene {
  const host = document.querySelector<HTMLElement>('.publication-scene');
  const svg = host?.querySelector('svg');
  if (!svg) throw new Error('当前没有已渲染画布');
  const metadata = JSON.parse(svg.querySelector('metadata')?.textContent ?? '{}');
  const anchors: NativeScene['anchors'] = {};
  for (const group of svg.querySelectorAll<SVGGElement>('[data-canonical-id]')) {
    // The body rect excludes repeat shadows and text/port bounding boxes.
    const body = group.querySelector<SVGRectElement>(':scope > rect[stroke-width]');
    const matrix = body?.getScreenCTM();
    if (!body || !matrix) continue;
    const canvas = { x: body.x.baseVal.value, y: body.y.baseVal.value };
    const screen = new DOMPoint(canvas.x, canvas.y).matrixTransform(matrix);
    anchors[group.getAttribute('data-node-id')!] = { canvas, screen: { x: screen.x, y: screen.y } };
  }
  return { documentId: svg.getAttribute('data-document-id') ?? '', revision: Number(svg.getAttribute('data-revision')),
    sourceDigest: metadata.sourceDigest ?? '', irDigest: metadata.irDigest ?? '', anchors,
    visibleIds: [...svg.querySelectorAll('[data-canonical-id]')].map(node => node.getAttribute('data-node-id')!).sort(),
    expandedIds: JSON.parse(host?.dataset.expandedIds ?? '[]'), pinnedIds: JSON.parse(host?.dataset.pinnedIds ?? '[]') };
}

/** Opt-in observer of ordinary controls; it never dispatches input or edits the canvas. */
export class NativePerformanceSession {
  private readonly trials: NativeTrial[] = [];
  private readonly frameTimes: number[] = [];
  private readonly pending = new Set<NativeTrial>();
  private frameId = 0;
  private active = true;
  private readonly startedAt = performance.now();
  private readonly startedScene = readScene();
  private readonly environment = { userAgent: navigator.userAgent, viewport: { width: innerWidth, height: innerHeight, devicePixelRatio },
    url: location.href, fonts: { status: document.fonts.status, loadedFaces: [...document.fonts].map(font => ({ family: font.family, status: font.status })) } };
  private readonly onProgress: (count: number) => void;

  constructor(onProgress: (count: number) => void) {
    this.onProgress = onProgress;
    studioTelemetry.reset();
    document.addEventListener('click', this.capture, true);
    document.addEventListener('pointerdown', this.capture, true);
    this.frameId = requestAnimationFrame(this.frame);
  }
  private readonly frame = (timestamp: number) => {
    if (!this.active) return;
    if (this.frameTimes.length < 20_000) this.frameTimes.push(timestamp);
    this.frameId = requestAnimationFrame(this.frame);
  };
  private readonly capture = (event: Event) => {
    if (!this.active || !(event.target instanceof Element) || this.trials.length >= 100) return;
    const treeButton = event.target.closest('.tree-toggle');
    const expandButton = event.target.closest('[data-expand-id]');
    if (!(event.type === 'click' && treeButton) && !(event.type === 'pointerdown' && expandButton)) return;
    const tree = treeButton?.closest<HTMLElement>('[data-tree-node-id]');
    const targetId = tree?.dataset.treeNodeId ?? expandButton?.getAttribute('data-expand-id');
    const targetTree = [...document.querySelectorAll<HTMLElement>('[data-tree-node-id]')].find(node => node.dataset.treeNodeId === targetId);
    if (!targetId || !targetTree || (treeButton instanceof HTMLButtonElement && treeButton.disabled)) return;
    const before = readScene();
    // Only unrelated visible pins are compared. Descendants may be hidden by collapse.
    const related = new Set([targetId, ...[...targetTree.querySelectorAll<HTMLElement>('[data-tree-node-id]')].map(node => node.dataset.treeNodeId!)]);
    before.pinnedIds = before.pinnedIds.filter(id => !related.has(id));
    const capturedAt = performance.now();
    const eventAt = event.timeStamp > capturedAt + 60_000 ? event.timeStamp - performance.timeOrigin : event.timeStamp;
    const trial: NativeTrial = { eventName: event.type as NativeTrial['eventName'], eventAt, capturedAt, trusted: event.isTrusted,
      targetId, operation: targetTree.getAttribute('aria-expanded') === 'true' ? 'collapse' : 'expand', before, after: null, error: null };
    this.trials.push(trial); this.pending.add(trial); this.onProgress(this.trials.length);
    // Geometry is sampled after two frames; this boundary is not the latency metric.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!this.pending.delete(trial)) return;
      try { trial.after = readScene(); }
      catch (failure) { trial.error = String(failure); }
      this.onProgress(this.trials.length);
    }));
  };
  stop() {
    this.dispose();
    for (const trial of this.pending) trial.error = 'Stopped before geometry sampling completed';
    this.pending.clear();
    const snapshot = studioTelemetry.snapshot();
    const trials = joinNativeTrials(this.trials, snapshot.eventTiming);
    const intervals = this.frameTimes.slice(1).map((timestamp, index) => timestamp - this.frameTimes[index]);
    const elapsedMs = performance.now() - this.startedAt;
    return { schemaVersion: 1, protocol: 'archcanvas-native-performance/1',
      measurement: { latency: 'native-event-timing-to-next-paint', durationThresholdMs: 16, durationQuantizationMs: 8,
        geometryBoundary: 'two-animation-frames-after-input', nativeInputSource: 'trusted-browser-events-not-human-certification' },
      environment: this.environment, bindingAtStart: this.startedScene, elapsedMs, trials, summary: summarizeNativeTrials(trials),
      frames: { frameCount: this.frameTimes.length, firstFrameAt: this.frameTimes[0] ?? null, lastFrameAt: this.frameTimes.at(-1) ?? null,
        intervals, intervalP95Ms: percentile(intervals), fps: this.frameTimes.length > 1 ? (this.frameTimes.length - 1) * 1000 / (this.frameTimes.at(-1)! - this.frameTimes[0]) : null,
        bufferTruncated: this.frameTimes.length === 20_000 }, snapshot,
      limitations: ['Missing or ambiguous Event Timing is null, including entries below the browser threshold.',
        'Geometry sampling does not prove paint; latency comes only from matched native browser Event Timing.',
        'Canvas pin displacement and screen anchor displacement use separate coordinate spaces.',
        'The observer adds measurement overhead; font faces do not identify hardware or installed fallback font bytes.',
        'A trusted browser event can come from automation and does not establish a human participant.'] };
  }
  dispose() {
    this.active = false; cancelAnimationFrame(this.frameId);
    document.removeEventListener('click', this.capture, true);
    document.removeEventListener('pointerdown', this.capture, true);
  }
}
