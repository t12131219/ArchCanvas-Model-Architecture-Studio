import test from 'node:test';
import assert from 'node:assert/strict';
import { StudioTelemetry } from '../src/perf.ts';

test('performance probe never reports paint before its second animation-frame boundary', () => {
  const original = globalThis.requestAnimationFrame;
  const callbacks: FrameRequestCallback[] = [];
  globalThis.requestAnimationFrame = callback => { callbacks.push(callback); return callbacks.length; };
  const telemetry = new StudioTelemetry();
  try {
    const id = telemetry.beginInteraction('expand');
    telemetry.endInteraction(id);
    assert.equal(telemetry.snapshot().interactions.length, 0);
    callbacks.shift()!(performance.now() + 16);
    assert.equal(telemetry.snapshot().interactions.length, 0);
    callbacks.shift()!(performance.now() + 32);
    const sample = telemetry.snapshot().interactions.find(item => item.id === id);
    assert.ok(sample);
    assert.equal(sample.name, 'expand');
    assert.ok((sample.handlerDurationMs ?? -1) >= 0);
    assert.ok(sample.paintAt !== null);
    assert.ok((sample.durationMs ?? -1) >= 0);
  } finally { telemetry.destroy(); globalThis.requestAnimationFrame = original; }
});

test('frame sampler reports a bounded fps sample and reset removes prior samples', async () => {
  const telemetry = new StudioTelemetry();
  const sample = await telemetry.sampleFrames(100);
  assert.equal(sample.requestedMs, 100);
  assert.ok(sample.frameCount >= 1);
  assert.ok(sample.fps >= 0);
  assert.ok(sample.p95FrameMs >= 0);
  assert.ok(sample.maxFrameMs >= sample.p95FrameMs);
  assert.ok(telemetry.snapshot().frameSamples.length === 1);
  telemetry.reset();
  assert.equal(telemetry.snapshot().interactions.length, 0);
  assert.equal(telemetry.snapshot().frameSamples.length, 0);
  telemetry.destroy();
});
