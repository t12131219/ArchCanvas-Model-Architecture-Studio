/**
 * Small, dependency free Studio performance probe.
 *
 * The probe records a two-animation-frame paint proxy from the visual handler
 * entry. This is not Event Timing or an INP measurement: it excludes the event
 * queue before the handler and only gives React and the browser a chance to
 * commit and paint the resulting SVG. It is exposed as
 * `window.__ARCHCANVAS_PERF__` so a browser runner can collect the same data as
 * a human reviewer without shipping a debug panel in the product UI.
 */

export type InteractionSample = {
  id: string;
  name: string;
  inputAt: number;
  handlerEndAt: number | null;
  handlerDurationMs: number | null;
  paintAt: number | null;
  durationMs: number | null;
};

export type LongTaskSample = { startAt: number; durationMs: number; name: string };
export type EventTimingSample = { name: string; startAt: number; durationMs: number; processingStart: number; processingEnd: number; interactionId: number; targetCanonicalNodeId?: string | null };
export type VisibilitySample = { at: number; state: string; hasFocus: boolean };

export type FrameSample = {
  requestedMs: number;
  elapsedMs: number;
  frameCount: number;
  fps: number;
  droppedFrames: number;
  p95FrameMs: number;
  maxFrameMs: number;
};

export type PerfSnapshot = {
  schemaVersion: 1;
  generatedAt: number;
  supported: { longTasks: boolean; animationFrames: boolean; eventTiming: boolean };
  visibility: { atStart: VisibilitySample; atEnd: VisibilitySample; changes: VisibilitySample[] };
  navigation: { domInteractiveMs: number | null; domContentLoadedMs: number | null; loadEventMs: number | null };
  paints: { firstPaintMs: number | null; firstContentfulPaintMs: number | null };
  interactions: InteractionSample[];
  longTasks: LongTaskSample[];
  eventTiming: EventTimingSample[];
  frameSamples: FrameSample[];
};

type AnimationFrame = (callback: FrameRequestCallback) => number;

function now(): number {
  return typeof performance !== 'undefined' && typeof performance.now === 'function' ? performance.now() : Date.now();
}

function raf(callback: FrameRequestCallback): number {
  const schedule = (globalThis as { requestAnimationFrame?: AnimationFrame }).requestAnimationFrame;
  if (schedule) return schedule(callback);
  return setTimeout(() => callback(now()), 16) as unknown as number;
}

function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * p) - 1))];
}

function timing(name: string): number | null {
  if (typeof performance === 'undefined' || typeof performance.getEntriesByType !== 'function') return null;
  const entry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  if (!entry) return null;
  const value = entry[name as keyof PerformanceNavigationTiming];
  return typeof value === 'number' && value > 0 ? value : null;
}

function paint(name: string): number | null {
  if (typeof performance === 'undefined' || typeof performance.getEntriesByType !== 'function') return null;
  const entry = performance.getEntriesByType('paint').find(item => item.name === name);
  return entry ? entry.startTime : null;
}

function visibility(): VisibilitySample {
  return { at: now(), state: typeof document === 'undefined' ? 'unavailable' : document.visibilityState, hasFocus: typeof document !== 'undefined' && document.hasFocus() };
}

export class StudioTelemetry {
  private readonly pending = new Map<string, InteractionSample>();
  private readonly interactions: InteractionSample[] = [];
  private readonly longTasks: LongTaskSample[] = [];
  private readonly eventTiming: EventTimingSample[] = [];
  private readonly frameSamples: FrameSample[] = [];
  private readonly observer: PerformanceObserver | null;
  private readonly eventObserver: PerformanceObserver | null;
  private observationWindowStart = now();
  private visibilityAtStart = visibility();
  private readonly visibilityChanges: VisibilitySample[] = [];
  private readonly visibilityChanged = () => {
    this.visibilityChanges.push(visibility());
    if (this.visibilityChanges.length > 200) this.visibilityChanges.splice(0, this.visibilityChanges.length - 200);
  };
  private sequence = 0;

  constructor() {
    let observer: PerformanceObserver | null = null;
    const Observer = (globalThis as { PerformanceObserver?: typeof PerformanceObserver }).PerformanceObserver;
    try {
      if (Observer && Observer.supportedEntryTypes?.includes('longtask')) {
        observer = new Observer(list => this.ingestLongTasks(list.getEntries()));
        observer.observe({ entryTypes: ['longtask'] });
      }
    } catch {
      observer = null;
    }
    this.observer = observer;
    let eventObserver: PerformanceObserver | null = null;
    try {
      if (Observer && Observer.supportedEntryTypes?.includes('event')) {
        eventObserver = new Observer(list => this.ingestEventTiming(list.getEntries()));
        eventObserver.observe({ type: 'event', durationThreshold: 16 } as PerformanceObserverInit);
      }
    } catch { eventObserver = null; }
    this.eventObserver = eventObserver;
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', this.visibilityChanged);
  }

  private ingestLongTasks(entries: PerformanceEntry[]): void {
    for (const entry of entries) {
      if (entry.startTime < this.observationWindowStart) continue;
      this.longTasks.push({ startAt: entry.startTime, durationMs: entry.duration, name: entry.name });
    }
    // Retention remains the last 200 delivered entries, not an all-input log.
    if (this.longTasks.length > 200) this.longTasks.splice(0, this.longTasks.length - 200);
  }

  private ingestEventTiming(entries: PerformanceEntry[]): void {
    for (const entry of entries) {
      // A delayed callback may already own entries that reset could not drain.
      if (entry.startTime < this.observationWindowStart) continue;
      const event = entry as PerformanceEntry & { processingStart: number; processingEnd: number; interactionId?: number; target?: EventTarget | null };
      const target = typeof Element !== 'undefined' && event.target instanceof Element ? event.target : null;
      const targetCanonicalNodeId = target?.closest('[data-expand-id]')?.getAttribute('data-expand-id') ?? target?.closest('[data-tree-node-id]')?.getAttribute('data-tree-node-id') ?? null;
      this.eventTiming.push({ name: event.name, startAt: event.startTime, durationMs: event.duration, processingStart: event.processingStart, processingEnd: event.processingEnd, interactionId: event.interactionId ?? 0, targetCanonicalNodeId });
    }
    if (this.eventTiming.length > 200) this.eventTiming.splice(0, this.eventTiming.length - 200);
  }

  private flushObservers(): void {
    if (this.observer) this.ingestLongTasks(this.observer.takeRecords());
    if (this.eventObserver) this.ingestEventTiming(this.eventObserver.takeRecords());
  }

  beginInteraction(name: string): string {
    const id = `interaction-${++this.sequence}`;
    this.pending.set(id, { id, name, inputAt: now(), handlerEndAt: null, handlerDurationMs: null, paintAt: null, durationMs: null });
    return id;
  }

  endInteraction(id: string): void {
    const sample = this.pending.get(id);
    if (!sample) return;
    sample.handlerEndAt = now();
    sample.handlerDurationMs = Math.max(0, sample.handlerEndAt - sample.inputAt);
    // The second frame is an explicit paint proxy, not proof of an actual
    // browser paint. Native Event Timing remains a separate observer below.
    raf(() => raf(timestamp => {
      const current = this.pending.get(id);
      if (!current) return;
      current.paintAt = timestamp;
      current.durationMs = Math.max(0, timestamp - current.inputAt);
      this.interactions.push({ ...current });
      if (this.interactions.length > 200) this.interactions.splice(0, this.interactions.length - 200);
      this.pending.delete(id);
    }));
  }

  sampleFrames(requestedMs = 1000): Promise<FrameSample> {
    const budget = Math.max(100, Math.min(10_000, requestedMs));
    return new Promise(resolve => {
      const start = now();
      let previous = start;
      let frames = 0;
      const intervals: number[] = [];
      const tick: FrameRequestCallback = timestamp => {
        const elapsed = timestamp - start;
        if (frames > 0) intervals.push(Math.max(0, timestamp - previous));
        previous = timestamp;
        frames += 1;
        if (elapsed < budget) {
          raf(tick);
          return;
        }
        const result: FrameSample = {
          requestedMs: budget,
          elapsedMs: Math.max(0, elapsed),
          frameCount: frames,
          fps: elapsed > 0 ? frames * 1000 / elapsed : 0,
          droppedFrames: intervals.filter(interval => interval > 50).length,
          p95FrameMs: percentile(intervals, .95),
          maxFrameMs: intervals.length ? Math.max(...intervals) : 0,
        };
        this.frameSamples.push(result);
        if (this.frameSamples.length > 20) this.frameSamples.splice(0, this.frameSamples.length - 20);
        resolve(result);
      };
      raf(tick);
    });
  }

  snapshot(): PerfSnapshot {
    // Include records already queued at this boundary. This does not force a
    // browser to produce entries that are still pending paint or delivery.
    this.flushObservers();
    return {
      schemaVersion: 1,
      generatedAt: now(),
      supported: { longTasks: this.observer !== null, animationFrames: typeof (globalThis as { requestAnimationFrame?: AnimationFrame }).requestAnimationFrame === 'function', eventTiming: this.eventObserver !== null },
      visibility: { atStart: this.visibilityAtStart, atEnd: visibility(), changes: [...this.visibilityChanges] },
      navigation: {
        domInteractiveMs: timing('domInteractive'),
        domContentLoadedMs: timing('domContentLoadedEventEnd'),
        loadEventMs: timing('loadEventEnd'),
      },
      paints: { firstPaintMs: paint('first-paint'), firstContentfulPaintMs: paint('first-contentful-paint') },
      interactions: [...this.interactions],
      longTasks: [...this.longTasks],
      eventTiming: [...this.eventTiming],
      frameSamples: [...this.frameSamples],
    };
  }

  reset(): void {
    // Discard queued records before opening the next window; timestamp checks
    // in both ingest paths also exclude old entries from delayed callbacks.
    this.observer?.takeRecords();
    this.eventObserver?.takeRecords();
    this.observationWindowStart = now();
    this.pending.clear();
    this.interactions.splice(0);
    this.longTasks.splice(0);
    this.eventTiming.splice(0);
    this.frameSamples.splice(0);
    this.visibilityAtStart = visibility();
    this.visibilityChanges.splice(0);
  }

  destroy(): void {
    this.observer?.disconnect();
    this.eventObserver?.disconnect();
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', this.visibilityChanged);
    this.reset();
  }
}

declare global {
  interface Window { __ARCHCANVAS_PERF__?: StudioTelemetry }
}

export const studioTelemetry = new StudioTelemetry();
if (typeof window !== 'undefined') window.__ARCHCANVAS_PERF__ = studioTelemetry;
