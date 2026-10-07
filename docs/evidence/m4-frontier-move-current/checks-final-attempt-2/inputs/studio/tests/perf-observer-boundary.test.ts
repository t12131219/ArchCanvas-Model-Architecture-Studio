import test from 'node:test';
import assert from 'node:assert/strict';
import { StudioTelemetry } from '../src/perf.ts';

type QueuedEntry = PerformanceEntry & {
  processingStart?: number; processingEnd?: number; interactionId?: number; target?: EventTarget | null;
};

function probe(run: (telemetry: StudioTelemetry, observers: Map<string, FakeObserver>, clock: { at: number }) => void) {
  const oldObserver = globalThis.PerformanceObserver;
  const oldPerformance = globalThis.performance;
  const oldElement = globalThis.Element;
  const clock = { at: 100 };
  const observers = new Map<string, FakeObserver>();
  class BoundElement {
    closest(selector: string) { return selector === '[data-expand-id]' ? this : null; }
    getAttribute(name: string) { return name === 'data-expand-id' ? 'encoder' : null; }
  }
  class Observer extends FakeObserver {
    static supportedEntryTypes = ['event', 'longtask'];
    observe(options: PerformanceObserverInit) { observers.set(options.type ?? options.entryTypes![0], this); }
  }
  Object.defineProperty(globalThis, 'PerformanceObserver', { configurable: true, writable: true, value: Observer });
  Object.defineProperty(globalThis, 'performance', { configurable: true, value: { now: () => clock.at, getEntriesByType: () => [] } });
  Object.defineProperty(globalThis, 'Element', { configurable: true, writable: true, value: BoundElement });
  const telemetry = new StudioTelemetry();
  try { run(telemetry, observers, clock); }
  finally {
    telemetry.destroy();
    Object.defineProperty(globalThis, 'PerformanceObserver', { configurable: true, writable: true, value: oldObserver });
    Object.defineProperty(globalThis, 'performance', { configurable: true, value: oldPerformance });
    Object.defineProperty(globalThis, 'Element', { configurable: true, writable: true, value: oldElement });
  }
}

// Queue and callback delivery are independent, as at a PerformanceObserver
// snapshot/reset boundary. The oracle below uses handwritten expected entries.
class FakeObserver {
  readonly queued: QueuedEntry[] = [];
  drains = 0;
  disconnected = false;
  private readonly callback: PerformanceObserverCallback;
  constructor(callback: PerformanceObserverCallback) { this.callback = callback; }
  takeRecords() { this.drains++; return this.queued.splice(0); }
  disconnect() { this.disconnected = true; this.queued.splice(0); }
  deliver(entries = this.queued.splice(0)) {
    this.callback({ getEntries: () => entries } as unknown as PerformanceObserverEntryList, this as unknown as PerformanceObserver);
  }
}

function event(at: number): QueuedEntry {
  const target = new globalThis.Element() as unknown as EventTarget;
  return { name: 'click', entryType: 'event', startTime: at, duration: 32,
    processingStart: at + 1, processingEnd: at + 5, interactionId: 7, target } as QueuedEntry;
}
function task(at: number): QueuedEntry { return { name: 'self', entryType: 'longtask', startTime: at, duration: 60 } as QueuedEntry; }

test('snapshot includes queued native timing and longtask exactly once without waiting for callback delivery', () => {
  probe((telemetry, observers, clock) => {
    observers.get('event')!.queued.push(event(110));
    observers.get('longtask')!.queued.push(task(111));
    clock.at = 200;
    const captured = telemetry.snapshot();
    assert.deepEqual(captured.eventTiming, [{ name: 'click', startAt: 110, durationMs: 32, processingStart: 111,
      processingEnd: 115, interactionId: 7, targetCanonicalNodeId: 'encoder' }]);
    assert.deepEqual(captured.longTasks, [{ name: 'self', startAt: 111, durationMs: 60 }]);
    assert.equal(observers.get('event')!.queued.length, 0);
    observers.get('event')!.deliver(); observers.get('longtask')!.deliver();
    assert.deepEqual(telemetry.snapshot().eventTiming, captured.eventTiming);
    assert.deepEqual(telemetry.snapshot().longTasks, captured.longTasks);
  });
});

test('reset discards already queued entries before the new measurement window', () => {
  probe((telemetry, observers, clock) => {
    observers.get('event')!.queued.push(event(110));
    observers.get('longtask')!.queued.push(task(111));
    clock.at = 200; telemetry.reset();
    assert.equal(observers.get('event')!.queued.length, 0);
    assert.equal(observers.get('longtask')!.queued.length, 0);
    observers.get('event')!.deliver(); observers.get('longtask')!.deliver();
    const captured = telemetry.snapshot();
    assert.deepEqual(captured.eventTiming, []); assert.deepEqual(captured.longTasks, []);
  });
});

test('late callbacks retain only entries that started in the current reset window', () => {
  probe((telemetry, observers, clock) => {
    // These old entries are already outside takeRecords when reset executes.
    const oldEvent = event(110), oldTask = task(111);
    clock.at = 200; telemetry.reset();
    clock.at = 300;
    observers.get('event')!.deliver([oldEvent, event(210)]);
    observers.get('longtask')!.deliver([oldTask, task(211)]);
    const captured = telemetry.snapshot();
    assert.deepEqual(captured.eventTiming.map(item => item.startAt), [210]);
    assert.deepEqual(captured.longTasks.map(item => item.startAt), [211]);
    assert.equal(captured.visibility.atStart.at, 200);
    assert.equal(captured.schemaVersion, 1);
  });
});

test('queued and callback ingestion share the same last-200 retention boundary', () => {
  probe((telemetry, observers, clock) => {
    observers.get('event')!.deliver(Array.from({ length: 100 }, (_, i) => event(110 + i)));
    observers.get('longtask')!.deliver(Array.from({ length: 100 }, (_, i) => task(110 + i)));
    observers.get('event')!.queued.push(...Array.from({ length: 105 }, (_, i) => event(210 + i)));
    observers.get('longtask')!.queued.push(...Array.from({ length: 105 }, (_, i) => task(210 + i)));
    clock.at = 400;
    const captured = telemetry.snapshot();
    assert.equal(captured.eventTiming.length, 200); assert.equal(captured.longTasks.length, 200);
    assert.equal(captured.eventTiming[0].startAt, 115); assert.equal(captured.longTasks[0].startAt, 115);
    assert.equal(captured.eventTiming.at(-1)!.startAt, 314); assert.equal(captured.longTasks.at(-1)!.startAt, 314);
  });
});
