#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

export function validateStudioPerformance(result) {
  if (result.schemaVersion !== 1 || result.scenario !== 'non-root-expand-collapse-fit') throw new Error('Unsupported Studio performance receipt schema');
  if (!result.environment?.viewport || !result.summary || !result.snapshot || !result.target?.canonicalNodeId || !(result.target.depth > 0)) throw new Error('Incomplete Studio performance receipt or root target');
  if (!result.binding?.documentId || !result.binding?.sourceDigest || !result.binding?.irDigest || !(result.binding.revisionAfter > result.binding.revisionBefore)) throw new Error('Receipt is not bound to a changed source-backed canvas');
  if (result.measurement?.latency !== 'two-animation-frame-paint-proxy' || result.measurement?.eventTiming !== 'observed-separately') throw new Error('Paint proxy and Event Timing must be distinguished');
  if (result.measurement.sampleCount < 20 || result.trials.length !== result.measurement.sampleCount * 2) throw new Error('Receipt must contain at least 20 expand/collapse pairs');
  const snapshot = result.snapshot;
  if (!Array.isArray(snapshot.interactions) || !Array.isArray(snapshot.frameSamples) || !Array.isArray(snapshot.longTasks) || !Array.isArray(snapshot.eventTiming)) throw new Error('Receipt arrays are missing');
  const interactionNames = new Set(snapshot.interactions.map(sample => sample.name));
  if (!interactionNames.has('visual:expand') || !interactionNames.has('visual:collapse') || !interactionNames.has('fit-canvas')) throw new Error('Receipt must have expand/collapse/fit samples');
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  for (const sample of snapshot.interactions) if (sample.durationMs !== null && !finite(sample.durationMs)) throw new Error('Non-finite interaction duration');
  for (const sample of snapshot.frameSamples) if (![sample.fps, sample.p95FrameMs, sample.maxFrameMs].every(finite)) throw new Error('Non-finite frame sample');
  for (const trial of result.trials) {
    if (!finite(trial.durationMs) || trial.beforeNodeCount < 1 || trial.afterNodeCount < 1) throw new Error('Invalid trial');
    if (trial.operation === 'expand' && trial.afterNodeCount <= trial.beforeNodeCount) throw new Error('Expansion did not add visible canonical nodes');
    if (trial.operation === 'collapse' && trial.afterNodeCount >= trial.beforeNodeCount) throw new Error('Collapse did not remove visible canonical nodes');
  }
  if (JSON.stringify(result.scene.before.canonicalVisibleNodeIds) !== JSON.stringify(result.scene.after.canonicalVisibleNodeIds)) throw new Error('Benchmark did not restore its starting frontier');
  for (const stats of Object.values(result.scene)) {
    if (new Set(stats.canonicalVisibleNodeIds).size !== stats.nodeCount || !stats.canonicalVisibleNodeIds.includes(result.target.canonicalNodeId)) throw new Error('Scene canonical counts do not match their IDs');
  }
  const percentile = (values, p) => {
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * p) - 1))];
  };
  const summary = result.summary;
  const visibility = result.environment.visibility;
  if (visibility && (JSON.stringify(visibility) !== JSON.stringify(snapshot.visibility) || !['visible', 'hidden'].includes(visibility.atStart.state) || !['visible', 'hidden'].includes(visibility.atEnd.state) || !Array.isArray(visibility.changes))) throw new Error('Visibility trace disagrees with the browser snapshot');
  const expand = result.trials.filter(trial => trial.operation === 'expand').map(trial => trial.durationMs);
  const collapse = result.trials.filter(trial => trial.operation === 'collapse').map(trial => trial.durationMs);
  if (expand.length !== result.measurement.sampleCount || collapse.length !== result.measurement.sampleCount) throw new Error('Expand/collapse sample totals disagree');
  if (summary.expandPaintProxyP50Ms !== percentile(expand, .5) || summary.expandPaintProxyP95Ms !== percentile(expand, .95) || summary.collapsePaintProxyP95Ms !== percentile(collapse, .95)) throw new Error('Paint proxy percentiles disagree with the measured trials');
  if ('expandHandlerP95Ms' in summary) {
    const expandHandler = result.trials.filter(trial => trial.operation === 'expand').map(trial => trial.handlerDurationMs);
    const collapseHandler = result.trials.filter(trial => trial.operation === 'collapse').map(trial => trial.handlerDurationMs);
    if (![...expandHandler, ...collapseHandler].every(finite) || summary.expandHandlerP95Ms !== percentile(expandHandler, .95) || summary.collapseHandlerP95Ms !== percentile(collapseHandler, .95)) throw new Error('Handler percentiles disagree with the measured trials');
  }
  if (result.idleFrameBaseline && (result.idleFrameBaseline.frames.requestedMs < 2000 || ![result.idleFrameBaseline.frames.fps, result.idleFrameBaseline.frames.p95FrameMs, result.idleFrameBaseline.frames.maxFrameMs].every(finite))) throw new Error('Invalid idle frame baseline');
  const frame = snapshot.frameSamples.at(-1);
  if (!frame || frame.requestedMs < 2000 || summary.fps !== frame.fps || summary.p95FrameMs !== frame.p95FrameMs || summary.maxFrameMs !== frame.maxFrameMs || summary.intervalsOver50Ms !== frame.droppedFrames) throw new Error('Frame summary disagrees with the measured interval sample');
  const maxLongTask = snapshot.supported?.longTasks ? snapshot.longTasks.reduce((max, task) => Math.max(max, task.durationMs), 0) : null;
  if (summary.maxLongTaskMs !== maxLongTask) throw new Error('Long-task summary disagrees with browser support and observation');
  return {
    target: result.target,
    viewport: result.environment.viewport,
    trials: result.trials.length,
    expandPaintProxyP95Ms: summary.expandPaintProxyP95Ms,
    collapsePaintProxyP95Ms: summary.collapsePaintProxyP95Ms,
    fps: summary.fps,
    intervalsOver50Ms: summary.intervalsOver50Ms,
    p95FrameMs: summary.p95FrameMs,
    maxLongTaskMs: summary.maxLongTaskMs,
    visibility: visibility ? { atStart: visibility.atStart.state, atEnd: visibility.atEnd.state, changes: visibility.changes.length } : null,
    idleFrameBaseline: result.idleFrameBaseline?.frames ?? null,
    expandHandlerP95Ms: summary.expandHandlerP95Ms ?? null,
    collapseHandlerP95Ms: summary.collapseHandlerP95Ms ?? null,
    status: 'validated',
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const file = process.argv[2] ?? 'docs/evidence/m4-studio-performance.json';
  const result = JSON.parse(await readFile(file, 'utf8'));
  console.log(JSON.stringify({ file, ...validateStudioPerformance(result) }, null, 2));
}
