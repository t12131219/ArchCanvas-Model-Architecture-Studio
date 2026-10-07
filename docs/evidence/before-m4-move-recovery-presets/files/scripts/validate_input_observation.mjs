#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

// Independent consistency checker: no observer, Studio, scene or history imports.
export function validateInputObservation(r) {
  const v1 = r?.schemaVersion === 1 && r.protocol === 'archcanvas-input-observation/1';
  const v2 = r?.schemaVersion === 2 && r.protocol === 'archcanvas-input-observation/2';
  const fail = message => { throw new Error(message); };
  const number = v => typeof v === 'number' && Number.isFinite(v);
  const positive = v => number(v) && v >= 0;
  const close = (a, b) => Math.abs(a - b) < .001;
  const hash = v => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const p95 = a => a.length ? [...a].sort((a, b) => a - b)[Math.ceil(a.length * .95) - 1] : null;
  const matrix = m => m && ['a', 'b', 'c', 'd', 'e', 'f'].every(k => number(m[k]));
  const rect = a => a && ['x', 'y', 'width', 'height'].every(k => number(a[k])) && a.width >= 0 && a.height >= 0;
  const stringIds = a => Array.isArray(a) && a.every(v => typeof v === 'string') && new Set(a).size === a.length;
  const publicTool = g => [null, 'pan', 'select'].includes(g.canvasTool) && [null, true, false].includes(g.handToolPressed);
  const canvasPanTrigger = e => e.type === 'pointerdown' && (v2
    ? e.target.inCanvas && !e.target.editingTarget && !e.target.canvasControl &&
      (e.button === 1 || e.button === 0 && (e.spaceHeld || e.target.canvasTool === 'pan' && e.target.handToolPressed === true))
    : e.button === 1 || e.spaceHeld === true);
  function geometry(g, full = false) {
    if (!g || !positive(g.at) || typeof g.documentId !== 'string' || !g.documentId || !Number.isInteger(g.revision) || g.revision < 0 ||
      !matrix(g.camera?.matrix) || !rect(g.viewport) || !g.objects || typeof g.objects !== 'object') fail('Invalid DOM binding/camera');
    if (g.frameRect !== null && !rect(g.frameRect)) fail('Invalid iframe rectangle');
    if (v2 && (!publicTool(g) || full && (typeof g.svgMarkup !== 'string' || !g.svgMarkup ||
      !Array.isArray(g.selectionMarkup) || !g.selectionMarkup.every(value => typeof value === 'string')))) fail('Missing public tool/document DOM evidence');
    for (const [id, o] of Object.entries(g.objects)) {
      if (o === null) continue;
      if (!rect(o.canvas) || !rect(o.screen) || !matrix(o.screenMatrix) || typeof o.intersectsViewport !== 'boolean' || typeof o.canonicalId !== 'string') fail(`Invalid object geometry: ${id}`);
      const b = o.canvas, m = o.screenMatrix;
      const corners = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
        .map(([x, y]) => ({ x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f }));
      const x = Math.min(...corners.map(p => p.x)), y = Math.min(...corners.map(p => p.y));
      const expected = { x, y, width: Math.max(...corners.map(p => p.x)) - x, height: Math.max(...corners.map(p => p.y)) - y };
      if (!['x', 'y', 'width', 'height'].every(k => close(expected[k], o.screen[k]))) fail('Screen/canvas transform disagrees');
      const v = g.viewport, visible = o.screen.x + o.screen.width > v.x && o.screen.x < v.x + v.width && o.screen.y + o.screen.height > v.y && o.screen.y < v.y + v.height;
      if (visible !== o.intersectsViewport) fail('Viewport intersection claim disagrees');
    }
    if (full && (!hash(g.sourceDigest) || !hash(g.irDigest) || !stringIds(g.visibleIds) || !stringIds(g.expandedIds) || !stringIds(g.pinnedIds))) fail('Invalid source/frontier binding');
    if (full) for (const id of Object.keys(g.objects)) if (g.objects[id] !== null && !g.visibleIds.includes(id)) fail('Observed object outside visible frontier');
  }
  if ((!v1 && !v2) || !['full', 'raf-only'].includes(r.measurement?.mode) ||
    r.measurement.runtimeAccess !== 'DOM-only' || r.measurement.coordinateSpace !== (v2 ? 'window-client-css-pixels' : 'iframe-client-css-pixels') ||
    r.measurement.latency !== 'matched-discrete-event-timing-only' || r.measurement.continuousInput !== 'observed-geometry-proxy-not-paint' ||
    r.measurement.frames !== 'raf-callback-cadence-not-presented-frames' || r.measurement.durationThresholdMs !== 16 || r.measurement.durationQuantizationMs !== 8) fail('Unsupported measurement contract');
  if (v2 && (r.measurement.panTrigger !== 'public-tool-space-middle/1' || r.measurement.panTerminal !== 'same-pointer-up-and-viewport-relative-camera/1' ||
    r.measurement.documentContinuity !== 'public-svg-and-frontier-not-hidden-document/1')) fail('Unsupported pan/document observation contract');
  if (!positive(r.startedAt) || !positive(r.stoppedAt) || r.stoppedAt < r.startedAt || !r.environment || !number(r.environment.timeOrigin) ||
    !positive(r.environment.viewport?.width) || !positive(r.environment.viewport?.height) || !positive(r.environment.viewport?.devicePixelRatio) ||
    !r.environment.supported || !Array.isArray(r.environment.scripts)) fail('Invalid observation environment');
  for (const name of ['trials', 'events', 'frames', 'eventTiming', 'longTasks', 'visibility', 'errors']) if (!Array.isArray(r[name])) fail(`Missing raw ${name}`);
  for (const [name, b] of Object.entries(r.buffers ?? {})) {
    if (!Number.isInteger(b.limit) || b.limit < 1 || !Number.isInteger(b.dropped) || b.dropped < 0) fail('Invalid truncation accounting');
    let values = r; for (const part of name.split('.')) values = values?.[part];
    if (!Array.isArray(values) || values.length > b.limit || b.dropped && values.length !== b.limit) fail('Buffer accounting disagrees');
  }
  const dropped = Object.entries(r.buffers ?? {}).filter(([, b]) => b.dropped).map(([name, b]) => ({ name, dropped: b.dropped }));
  const complete = !dropped.length;
  geometry(r.bindingAtStart, true);
  const eventMap = new Map(); let lastEventAt = -Infinity;
  const eventTypes = new Set(['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'click', 'keydown', 'keyup', 'wheel']);
  if (v2) { eventTypes.add('lostpointercapture'); eventTypes.add('blur'); }
  for (const e of r.events) {
    if (typeof e.id !== 'string' || eventMap.has(e.id) || !eventTypes.has(e.type) || !positive(e.eventAt) || !positive(e.capturedAt) || e.eventAt < lastEventAt ||
      typeof e.trusted !== 'boolean' || !e.target || !(e.target.token === null || typeof e.target.token === 'string')) fail('Invalid or unordered raw input');
    if (e.eventAt > e.capturedAt + 8 || e.capturedAt < r.startedAt || e.capturedAt > r.stoppedAt) fail('Input clock/window disagrees');
    if (e.type.startsWith('pointer') && ![e.x, e.y, e.pointerId, e.button, e.buttons].every(number)) fail('Missing pointer scalars');
    if (v2 && (!publicTool(e.target) || !['inCanvas', 'editingTarget', 'canvasControl'].every(key => typeof e.target[key] === 'boolean') ||
      typeof e.spaceHeld !== 'boolean' || e.viewport !== null && !rect(e.viewport) || e.target.inCanvas && !rect(e.viewport))) fail('Missing input-time public tool/viewport facts');
    if (v2 && e.type === 'lostpointercapture' && !number(e.pointerId)) fail('Missing lost-capture pointer identity');
    if (e.type === 'wheel' && ![e.x, e.y, e.deltaX, e.deltaY, e.deltaMode].every(number)) fail('Missing wheel scalars');
    if (e.coalesced !== undefined && (!Array.isArray(e.coalesced) || !e.coalesced.every(c => positive(c.at) && number(c.x) && number(c.y)))) fail('Invalid coalesced input');
    eventMap.set(e.id, e); lastEventAt = e.eventAt;
  }
  for (const e of r.eventTiming) {
    if (typeof e.name !== 'string' || ['pointermove', 'wheel'].includes(e.name) || ![e.startAt, e.durationMs, e.processingStart, e.processingEnd].every(positive) || e.processingStart < e.startAt || e.processingEnd < e.processingStart ||
      !Number.isInteger(e.interactionId) || e.interactionId < 0 || !(e.targetToken === null || typeof e.targetToken === 'string')) fail('Invalid native Event Timing entry');
  }
  if (!r.environment.supported.eventTimingObserved && r.eventTiming.length || !r.environment.supported.longTasksObserved && r.longTasks.length) fail('Unsupported observer produced native entries');
  let lastFrameAt = -Infinity;
  for (const f of r.frames) {
    if (!positive(f.at) || !positive(f.observedAt) || f.at < lastFrameAt || f.observedAt + 8 < f.at || f.observedAt < r.startedAt || f.observedAt > r.stoppedAt) fail('Invalid frame clock/window');
    if (f.geometry) geometry(f.geometry);
    lastFrameAt = f.at;
  }
  for (const l of r.longTasks) if (!positive(l.at) || !positive(l.durationMs) || l.durationMs < 50) fail('Invalid long task');
  for (const v of r.visibility) if (!positive(v.at) || !['visible', 'hidden'].includes(v.state) || typeof v.hasFocus !== 'boolean' || typeof v.topHasFocus !== 'boolean') fail('Invalid visibility/focus evidence');
  if (r.measurement.mode === 'raf-only' && (r.trials.length || r.events.length || r.eventTiming.length || r.longTasks.length)) fail('raf-only control contains active observer data');
  const overhead = {};
  for (const name of ['sceneReads', 'inputCallbacks', 'frameCallbacks', 'performanceCallbacks']) {
    const values = r.overhead?.[name];
    if (!Array.isArray(values) || !values.every(v => positive(v.at) && positive(v.durationMs))) fail('Invalid observer self-cost');
    overhead[name] = { samples: values.length, p95Ms: p95(values.map(v => v.durationMs)), maxMs: values.length ? Math.max(...values.map(v => v.durationMs)) : null };
  }
  const matches = [];
  const discrete = new Set(['pointerdown', 'pointerup', 'click', 'keydown', 'keyup']);
  // Build the entire candidate graph before assigning any edge. An entry that
  // could belong to two inputs cannot be given to the first one by array order.
  // Unassigned inputs also compete: a trial must not borrow an outside input.
  const matchingInputs = r.events.filter(raw => raw.trusted && discrete.has(raw.type) && raw.target.token);
  const inputCandidates = new Map(), entryCandidates = new Map();
  for (const raw of matchingInputs) {
    const candidates = r.eventTiming.flatMap((entry, index) => entry.interactionId > 0 && entry.name === raw.type &&
      entry.targetToken === raw.target.token && Math.abs(entry.startAt - raw.eventAt) <= 8 ? [index] : []);
    inputCandidates.set(raw.id, candidates);
    for (const index of candidates) {
      if (!entryCandidates.has(index)) entryCandidates.set(index, []);
      entryCandidates.get(index).push(raw.id);
    }
  }
  for (const raw of matchingInputs) {
    if (!raw.trialId) continue;
    const candidates = inputCandidates.get(raw.id);
    const unique = candidates.length === 1 && entryCandidates.get(candidates[0]).length === 1;
    const match = unique ? { index: candidates[0], entry: r.eventTiming[candidates[0]] } : null;
    matches.push({ inputId: raw.id, trialId: raw.trialId, nativeEntryIndex: match?.index ?? null,
      nativeDurationMs: match?.entry.durationMs ?? null, interactionId: match?.entry.interactionId ?? null,
      inputCandidateCount: candidates.length,
      candidateEntryInputCounts: candidates.map(index => ({ nativeEntryIndex: index, inputs: entryCandidates.get(index).length })),
      missingReason: match ? null : candidates.length ? 'ambiguous' : 'unavailable-below-threshold-detached-or-truncated' });
  }
  const visualSignature = g => JSON.stringify([g.camera.matrix, Object.entries(g.objects).map(([id, o]) => [id, o?.canvas ?? null, o?.screen ?? null, o?.label ?? null])]);
  const signature = g => JSON.stringify([g.revision, visualSignature(g)]);
  const delta = (a, b) => a && b ? { x: b.x - a.x, y: b.y - a.y, distancePx: Math.hypot(b.x - a.x, b.y - a.y) } : null;
  function frameSummary(frames) {
    const intervals = frames.slice(1).map((f, i) => f.at - frames[i].at);
    return { frames: frames.length, intervalP95Ms: p95(intervals), maxIntervalMs: intervals.length ? Math.max(...intervals) : null,
      fps: frames.length > 1 && frames.at(-1).at > frames[0].at ? (frames.length - 1) * 1000 / (frames.at(-1).at - frames[0].at) : null };
  }
  const resultTrials = []; let previousFinishedAt = r.startedAt;
  const trialIds = new Set(r.trials.map(t => t.id));
  if (trialIds.size !== r.trials.length) fail('Duplicate trial identity');
  for (const raw of r.events) if (raw.trialId !== null && !trialIds.has(raw.trialId)) fail('Raw input references unknown trial');
  for (const f of r.frames) if (f.trialId !== null && !trialIds.has(f.trialId)) fail('Frame references unknown trial');
  for (const t of r.trials) {
    if (!['drag', 'pan', 'zoom', 'undo', 'redo', 'toggle', 'pin'].includes(t.spec?.operation) || !['finished', 'stopped-pending', 'no-input'].includes(t.status) ||
      ![t.spec.targetIds, t.spec.anchorIds, t.spec.pinnedIds].every(stringIds) || !positive(t.armedAt) || !positive(t.finishedAt) ||
      t.armedAt < previousFinishedAt || t.finishedAt < t.armedAt || t.finishedAt > r.stoppedAt) fail('Invalid trial operation/timeline');
    previousFinishedAt = t.finishedAt;
    const inputs = r.events.filter(e => e.trialId === t.id), frames = r.frames.filter(f => f.trialId === t.id);
    if (t.before) geometry(t.before, true); geometry(t.after, true);
    if (t.status === 'no-input') {
      if (t.before !== null || inputs.length || frames.length) fail('No-input trial contains active evidence');
      const outside = r.events.filter(e => e.trusted && e.trialId === null && e.capturedAt >= t.armedAt && e.capturedAt <= t.finishedAt);
      const starts = outside.filter(e => ['pointerdown', 'keydown', 'wheel'].includes(e.type));
      const wrongDragTarget = t.spec.operation === 'drag' && starts.some(e => e.type === 'pointerdown' && e.target.kind === 'node' && !t.spec.targetIds.includes(e.target.nodeId));
      const wrongPanMode = v2 && t.spec.operation === 'pan' && starts.some(e => e.type === 'pointerdown' && e.target.inCanvas && e.button === 0 && !canvasPanTrigger(e));
      resultTrials.push({ id: t.id, operation: t.spec.operation, status: t.status, requestedTargets: t.spec.targetIds,
        observed: false, operationSucceeded: false, missingReason: wrongDragTarget ? 'requested-target-not-hit' : wrongPanMode ? 'left-pointer-without-active-pan-trigger' : 'no-matching-requested-trigger',
        outsideRequestedTrialInputCount: outside.length,
        outsideRequestedTrialStarts: starts.map(e => ({ inputId: e.id, type: e.type, targetNodeId: e.target.nodeId, targetKind: e.target.kind,
          requestedTargetMatched: t.spec.targetIds.includes(e.target.nodeId), eventAt: e.eventAt, x: e.x, y: e.y,
          ...(v2 ? { canvasTool: e.target.canvasTool, handToolPressed: e.target.handToolPressed, spaceHeld: e.spaceHeld } : {}) })),
        scope: 'Unassigned actual inputs are diagnostic; they do not provide requested-trial geometry or latency coverage.' }); continue;
    }
    if (!t.before || complete && (!inputs.length || t.firstEventId !== inputs[0].id || t.lastEventId !== inputs.at(-1).id)) fail('Missing trial input binding');
    const start = eventMap.get(t.firstEventId);
    if (start && !start.trusted) fail('Trial began with synthetic input');
    if (start && t.spec.operation === 'drag' && (start.type !== 'pointerdown' || start.button !== 0 || start.target.kind !== 'node' || !t.spec.targetIds.includes(start.target.nodeId))) fail('Drag began on a different control/target');
    if (start && v2 && t.spec.operation === 'drag' && canvasPanTrigger(start)) fail('Object drag began in pan mode');
    if (start && t.spec.operation === 'pan' && !canvasPanTrigger(start)) fail('Pan lacks its actual input trigger');
    if (start && v2 && t.spec.operation === 'pan' && (start.target.canvasTool !== t.before.canvasTool || start.target.handToolPressed !== t.before.handToolPressed ||
      !same(start.viewport, t.before.viewport))) fail('Pan trigger and pre-input public DOM disagree');
    if (start && t.spec.operation === 'toggle' && (start.type !== 'pointerdown' || start.target.kind !== 'toggle' || !t.spec.targetIds.includes(start.target.nodeId))) fail('Toggle began on a different control/target');
    if (start && ['undo', 'redo', 'pin', 'zoom'].includes(t.spec.operation)) {
      const action = start.type === 'pointerdown' && start.target.action === t.spec.operation;
      const shortcut = start.type === 'keydown' && (t.spec.operation === 'zoom' ? start.key?.toLowerCase() === 'f' :
        ['undo', 'redo'].includes(t.spec.operation) && (start.ctrl || start.meta) && start.key?.toLowerCase() === 'z' && start.shift === (t.spec.operation === 'redo'));
      const wheel = t.spec.operation === 'zoom' && start.type === 'wheel' && start.target.kind !== 'other';
      if (!action && !shortcut && !wheel) fail('Trial lacks its actual control/shortcut input');
    }
    if (inputs.some(e => e.capturedAt < t.armedAt || e.capturedAt > t.finishedAt) || frames.some(f => f.observedAt > t.finishedAt || !f.geometry || f.geometry.documentId !== t.before.documentId)) fail('Trial input/frames outside bound window');
    const bindingValid = t.before.documentId === t.after.documentId && t.before.sourceDigest === t.after.sourceDigest && t.before.irDigest === t.after.irDigest;
    if (!bindingValid) fail('Source/IR changed during visual trial');
    const ids = [...new Set([...t.spec.targetIds, ...t.spec.anchorIds, ...t.spec.pinnedIds])];
    if (ids.some(id => !Object.hasOwn(t.before.objects, id) || !Object.hasOwn(t.after.objects, id))) fail('Selected object coverage missing');
    if (t.spec.pinnedIds.some(id => !t.before.pinnedIds.includes(id))) fail('Specified protected object was not pinned');
    const changes = Object.fromEntries(ids.map(id => [id, { canvas: delta(t.before.objects[id]?.canvas, t.after.objects[id]?.canvas), screen: delta(t.before.objects[id]?.screen, t.after.objects[id]?.screen),
      screenMeasured: !!t.before.objects[id]?.intersectsViewport && !!t.after.objects[id]?.intersectsViewport }]));
    const revisionDelta = t.after.revision - t.before.revision, a = t.before.camera.matrix, b = t.after.camera.matrix;
    const cameraChanged = !same(a, b), scaleChanged = !close(a.a, b.a) || !close(a.b, b.b) || !close(a.c, b.c) || !close(a.d, b.d);
    const trusted = inputs.filter(e => e.trusted), firstDown = trusted.find(e => e.type === 'pointerdown'), up = firstDown && trusted.find(e => e.type === 'pointerup' && e.pointerId === firstDown.pointerId && e.eventAt >= firstDown.eventAt);
    const moves = firstDown ? trusted.filter(e => e.type === 'pointermove' && e.pointerId === firstDown.pointerId && e.eventAt >= firstDown.eventAt && (!up || e.eventAt <= up.eventAt)) : [];
    const upIndex = up ? trusted.indexOf(up) : trusted.length;
    const activeInputs = trusted.slice(firstDown ? trusted.indexOf(firstDown) : 0, upIndex);
    const cancelled = v2 ? activeInputs.some(e => ['pointercancel', 'lostpointercapture'].includes(e.type) && e.pointerId === firstDown?.pointerId ||
      e.type === 'blur' || e.type === 'keydown' && e.key === 'Escape') : trusted.some(e => e.type === 'pointercancel');
    const deltaMoved = t.spec.targetIds.some(id => changes[id]?.canvas?.distancePx > .001);
    const selectedCanvasUnchanged = ids.every(id => changes[id]?.canvas?.distancePx === 0);
    const toggleChanged = t.spec.targetIds.length > 0 && t.spec.targetIds.some(id => t.before.expandedIds.includes(id) !== t.after.expandedIds.includes(id));
    const pinChanged = !same([...t.before.pinnedIds].sort(), [...t.after.pinnedIds].sort());
    const shapeChanged = visualSignature(t.before) !== visualSignature(t.after) || !same(t.before.expandedIds, t.after.expandedIds) || pinChanged;
    const publicDocumentContinuity = v2 ? {
      matched: revisionDelta === 0 && same(t.before.visibleIds, t.after.visibleIds) && same(t.before.expandedIds, t.after.expandedIds) &&
        same(t.before.pinnedIds, t.after.pinnedIds) && t.before.svgMarkup === t.after.svgMarkup && same(t.before.selectionMarkup, t.after.selectionMarkup),
      hiddenCanvasCertified: false, historyCertified: false, scope: 'public SVG/frontier/pins/selection only',
    } : { matched: null, hiddenCanvasCertified: false, historyCertified: false, scope: 'unavailable-in-v1' };
    let panTerminal = null;
    if (t.spec.operation === 'pan') {
      panTerminal = { status: 'unmeasured', expectedCamera: null, actualCamera: b,
        reason: v2 ? !complete ? 'truncated-input-buffer' : !firstDown || !up ? 'missing-same-pointer-down-up' : null : 'unavailable-in-v1',
        presentedPaintCertified: false };
      if (v2 && complete && firstDown && up) {
        const ups = trusted.filter(e => e.type === 'pointerup' && e.pointerId === firstDown.pointerId && e.eventAt >= firstDown.eventAt);
        if (ups.length !== 1) panTerminal.reason = 'ambiguous-same-pointer-up';
        else if (!rect(firstDown.viewport) || !rect(up.viewport)) panTerminal.reason = 'missing-input-time-viewport';
        else if (t.after.at < up.capturedAt) panTerminal.reason = 'after-snapshot-precedes-terminal-input';
        else {
          const dx = (up.x - up.viewport.x) - (firstDown.x - firstDown.viewport.x);
          const dy = (up.y - up.viewport.y) - (firstDown.y - firstDown.viewport.y);
          const expectedCamera = { ...a, e: a.e + dx, f: a.f + dy };
          const matchesCamera = Object.keys(expectedCamera).every(key => close(expectedCamera[key], b[key]));
          Object.assign(panTerminal, { status: matchesCamera ? 'matched' : 'mismatch', reason: null, expectedCamera,
            deltaCssPx: { x: dx, y: dy }, downInputId: firstDown.id, upInputId: up.id });
        }
      }
    }
    let operationSucceeded = false;
    if (t.spec.operation === 'drag') operationSucceeded = !!firstDown && !!up && moves.length > 0 && !cancelled && revisionDelta === 1 && deltaMoved;
    if (t.spec.operation === 'pan') operationSucceeded = !!firstDown && !!up && (v2 || moves.length > 0) && !cancelled && revisionDelta === 0 && cameraChanged &&
      !scaleChanged && selectedCanvasUnchanged && (!v2 || complete && panTerminal.status === 'matched' && publicDocumentContinuity.matched);
    if (t.spec.operation === 'zoom') operationSucceeded = trusted.length > 0 && revisionDelta === 0 && scaleChanged && selectedCanvasUnchanged;
    if (t.spec.operation === 'toggle') operationSucceeded = trusted.length > 0 && revisionDelta === 1 && toggleChanged;
    if (t.spec.operation === 'pin') operationSucceeded = trusted.length > 0 && revisionDelta === 1 && pinChanged;
    if (['undo', 'redo'].includes(t.spec.operation)) operationSucceeded = trusted.length > 0 && revisionDelta === 1 && shapeChanged;
    const changedFrames = []; let lastSignature = signature(t.before);
    for (const f of frames) { const next = signature(f.geometry); if (next !== lastSignature) changedFrames.push(f); lastSignature = next; }
    const continuousProxies = inputs.filter(e => e.trusted && ['pointermove', 'wheel'].includes(e.type)).map(e => {
      const next = changedFrames.find(f => f.observedAt >= e.capturedAt);
      return { inputId: e.id, observedAt: next?.observedAt ?? null, inputToObservedChangeProxyMs: next ? next.observedAt - e.eventAt : null,
        presentedPaintCertified: false, causalInputIdentified: false };
    });
    const activeLongTasks = r.longTasks.filter(l => l.at < t.finishedAt && l.at + l.durationMs > t.before.at);
    resultTrials.push({ id: t.id, operation: t.spec.operation, observed: true, finished: t.status === 'finished', operationSucceeded,
      sourceBindingValid: bindingValid, revisionDelta, trustedInputs: trusted.length, trustedPointerMoves: moves.length,
      pointerDownUpObserved: !!firstDown && !!up, cancelled, cameraChanged, scaleChanged, changes,
      ...(v2 || t.spec.operation === 'pan' ? { panTerminal, publicDocumentContinuity } : {}),
      protectedObjects: t.spec.pinnedIds.map(id => ({ id, ...changes[id] })), frameCadence: frameSummary(frames), continuousProxies,
      activeLongTasks: activeLongTasks.length, maxActiveLongTaskMs: activeLongTasks.length ? Math.max(...activeLongTasks.map(l => l.durationMs)) : null });
  }
  const interactionDurations = new Map();
  for (const m of matches) if (m.interactionId !== null) interactionDurations.set(m.interactionId, Math.max(m.nativeDurationMs, interactionDurations.get(m.interactionId) ?? 0));
  const idleIntervals = r.frames.slice(1).flatMap((f, i) => f.trialId === null && r.frames[i].trialId === null ? [f.at - r.frames[i].at] : []);
  return { status: 'validated-engineering-observation', completeBuffers: complete, dropped, errors: r.errors,
    inputProtocol: r.protocol,
    measurementEnvironment: r.environment.isIframe ? 'same-origin-iframe' : 'top-level', humanCertified: false, presentedDragPaintCertified: false,
    latency: { supported: r.environment.supported.eventTimingObserved, eligibleDiscreteInputs: matches.length,
      matchedDiscreteInputs: matches.filter(m => m.nativeEntryIndex !== null).length, matchedInteractions: interactionDurations.size,
      matchedInteractionP95Ms: p95([...interactionDurations.values()]), matches,
      scope: 'matched discrete interaction subset; not continuous drag latency or overall page INP' },
    frameCadence: frameSummary(r.frames), idleCadence: { intervals: idleIntervals.length, intervalP95Ms: p95(idleIntervals),
      fps: idleIntervals.length && idleIntervals.reduce((a, b) => a + b, 0) > 0 ? idleIntervals.length * 1000 / idleIntervals.reduce((a, b) => a + b, 0) : null },
    observerSelfCost: overhead, selfCostCategoriesOverlap: true, trials: resultTrials,
    limitation: 'Consistency and committed DOM facts only; no hardware/font lock, paint, complete native latency, CPU-cause, persistence or human aesthetics certification.' };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(JSON.stringify(validateInputObservation(JSON.parse(await readFile(process.argv[2], 'utf8'))), null, 2));
}
