/** Independent fixed-window observer. No product imports, dispatch or private globals. */
const WARMUP_MS = 2000, CAPTURE_MS = 20000, INPUT_DEADLINE_MS = 10000, DRAIN_MS = 2000;
const INPUT_TYPES = ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'lostpointercapture', 'click', 'keydown', 'keyup', 'wheel'];
const DISCRETE = new Set(['pointerdown', 'pointerup', 'click', 'keydown', 'keyup']);
const OPERATIONS = new Set(['idle', 'click', 'drag', 'pan', 'zoom', 'toggle', 'undo', 'redo', 'pin']);
const plainRect = rect => rect && ({ x: rect.x, y: rect.y, width: rect.width, height: rect.height });

export function measuredSurfaceCoverage(topWindow, surface) {
  const rect = plainRect(surface.getBoundingClientRect());
  const viewport = { width: topWindow.innerWidth, height: topWindow.innerHeight, dpr: topWindow.devicePixelRatio };
  const fullyInsideTopViewport = rect.x >= 0 && rect.y >= 0 && rect.x + rect.width <= viewport.width + .5 && rect.y + rect.height <= viewport.height + .5;
  return { rect, viewport, fullyInsideTopViewport, externalOcclusionKnown: false };
}

export function createFixedWindowObserver(w, options) {
  const { topWindow, surface, surfaceKind, context, mode, label, operation, targetIds, onPhase, onComplete } = options;
  if (!['raf-only', 'full'].includes(mode) || !['control', 'studio'].includes(surfaceKind) || !OPERATIONS.has(operation)) throw new Error('Invalid mode, surface or operation');
  if (!Array.isArray(targetIds) || targetIds.some(id => typeof id !== 'string')) throw new Error('Invalid target IDs');
  const doc = w.document; // Same-origin check occurs before any recording.
  if (!doc?.querySelector) throw new Error('Same-origin public DOM required');
  if (surfaceKind === 'studio' && !doc.querySelector('.publication-scene svg')) throw new Error('Select and render a real Studio document before measuring');
  const clock = () => w.performance.now();
  const utc = () => new Date().toISOString();
  let used = false, running = false, phase = 'unstarted', rafId = 0, inputSequence = 0, tokenSequence = 0;
  const timers = [], listeners = [], observers = [], targetTokens = new WeakMap();
  const data = {
    protocol: 'archcanvas-fixed-window-performance-observation/1', status: 'unstarted', mode, label, operation,
    surfaceKind, targetIds: [...targetIds], context, humanParticipants: 0,
    measurement: { runtimeAccess: 'public-DOM-only', frames: 'callback-cadence-not-presented-frames',
      continuousLatency: 'public-DOM-observation-not-input-to-paint', nativeDiscreteLatency: 'one-to-one-matched-EventTiming-only',
      warmupMs: WARMUP_MS, captureMs: CAPTURE_MS, inputDeadlineMs: INPUT_DEADLINE_MS,
      minimumPostInputSettleMs: CAPTURE_MS - INPUT_DEADLINE_MS, deliveryDrainMs: DRAIN_MS,
      eventTimingRequestedDurationThresholdMs: 16, eventTimingCommonQuantizationMs: 8,
      matchingToleranceMs: 2, fullGeometry: 'configured-targets-and-camera-each-callback',
      directOverheadCategoriesOverlap: true, externalPresentationKnown: false },
    deadlines: {}, boundaries: [], environment: null, endEnvironment: null,
    bindingBefore: null, bindingAfter: null, frames: [], inputs: [], eventTiming: [], longTasks: [],
    environmentChanges: [], lifecycle: [], drains: [],
    overhead: { snapshots: [], geometry: [], inputs: [], frames: [], performance: [], environment: [] },
    buffers: {}, errors: [], denominators: null, gestures: null, integrity: null,
    supported: { nativeInputsObserved: mode === 'full', eventTimingAvailable: false, eventTimingObserved: false,
      longTasksAvailable: false, longTasksObserved: false },
    presentedPerformanceCertified: false, overallInpCertified: false, modelsExecuted: false,
    limitations: [
      'rAF timestamps and DOM geometry do not prove actual presentation or continuous input-to-paint.',
      'This observer is a new measurement pipeline; it does not reproduce every old full-observer allocation or prove zero perturbation.',
      'Direct callback costs omit browser delivery, GC and renderer/system work; geometry costs are nested within frame costs.',
      'Missing or ambiguous native EventTiming entries stay unknown; takeRecords cannot force pending entries to finish.',
      'FontFaceSet and CSS families do not bind actual resolved glyph font bytes.',
      'DOM focus/visibility/coverage do not prove external window visibility, no occlusion or display refresh.',
      'Trusted automation is native browser input evidence, not an OS hardware/human participant.',
      'Raf-only deliberately observes no native input or EventTiming; use separate actual tool action logs.',
      'Matched-subset interaction durations do not establish all-page INP; control durations are never subtracted.'
    ]
  };
  function push(path, value, limit = 50000) {
    let list = data;
    for (const part of path.split('.')) list = list[part];
    const buffer = data.buffers[path] ??= { limit, attempted: 0, dropped: 0 };
    buffer.attempted++;
    if (list.length < limit) list.push(value); else buffer.dropped++;
  }
  function fail(where, error) { push('errors', { at: clock(), phase, where, error: String(error) }, 1000); }
  function timed(category, operationFn, extra = {}) {
    const at = clock();
    try { return operationFn(); }
    finally { push(`overhead.${category}`, { at, endAt: clock(), durationMs: clock() - at, phase, ...extra }); }
  }
  function phaseAt(at) {
    if (data.deadlines.captureStart == null) return 'warmup';
    if (at < data.deadlines.captureStart) return 'warmup';
    if (at < data.deadlines.captureEnd) return 'capture';
    if (at < data.deadlines.drainEnd) return 'drain';
    return 'after-planned-drain';
  }
  function token(target) {
    if (!(target instanceof w.Element)) return null;
    if (!targetTokens.has(target)) targetTokens.set(target, `target-${++tokenSequence}`);
    return targetTokens.get(target);
  }
  function targetFacts(target) {
    if (!(target instanceof w.Element)) return { token: null, inMeasuredSurface: false, tag: null, id: null, nodeId: null };
    const card = target.closest('[data-canonical-id][data-node-id]');
    const toggle = target.closest('[data-expand-id]');
    const button = target.closest('button');
    return { token: token(target), inMeasuredSurface: surfaceKind === 'studio' ? true : surface.contains(target),
      tag: target.tagName.toLowerCase(), id: target.id || null,
      nodeId: toggle?.getAttribute('data-expand-id') ?? card?.getAttribute('data-node-id') ?? null,
      label: button?.getAttribute('aria-label') ?? button?.getAttribute('title') ?? null,
      editingTarget: !!target.closest('input,textarea,select,[contenteditable]'),
      inCanvas: !!target.closest('.canvas-viewport'), canvasTool: doc.querySelector('.canvas-viewport')?.getAttribute('data-canvas-tool') ?? null };
  }
  function flags(eventType = 'snapshot') {
    return { at: clock(), phase: phaseAt(clock()), eventType, visibility: doc.visibilityState, focused: doc.hasFocus(),
      topVisibility: topWindow.document.visibilityState, topFocused: topWindow.document.hasFocus(),
      coverage: measuredSurfaceCoverage(topWindow, surface) };
  }
  function geometry() {
    return timed('geometry', () => {
      if (surfaceKind === 'control') {
        const target = doc.getElementById('control-target');
        return { at: clock(), controlTarget: plainRect(target?.getBoundingClientRect()), text: target?.textContent ?? null,
          coverage: measuredSurfaceCoverage(topWindow, surface) };
      }
      const host = doc.querySelector('.publication-scene'), svg = host?.querySelector('svg'), paper = doc.querySelector('.paper');
      if (!svg || !paper) throw new Error('Public Studio scene disappeared');
      const objects = {};
      for (const id of targetIds) {
        const group = svg.querySelector(`[data-canonical-id][data-node-id="${w.CSS.escape(id)}"]`);
        const body = group?.querySelector(':scope > rect[stroke-width]');
        const screen = plainRect(body?.getBoundingClientRect());
        objects[id] = body ? { screen, canvas: Object.fromEntries(['x', 'y', 'width', 'height'].map(key => [key, body.getAttribute(key)])),
          canonicalId: group.getAttribute('data-canonical-id'), label: group.getAttribute('aria-label') } : null;
      }
      return { at: clock(), documentId: svg.getAttribute('data-document-id'), revision: svg.getAttribute('data-revision'),
        cameraTransform: w.getComputedStyle(paper).transform,
        canvasViewport: plainRect(doc.querySelector('.canvas-viewport')?.getBoundingClientRect()), objects,
        coverage: measuredSurfaceCoverage(topWindow, surface) };
    });
  }
  function publicSnapshot() {
    return timed('snapshots', () => {
      const result = { at: clock(), flags: flags(), geometry: geometry(),
        scriptUrls: [...doc.scripts].map(element => element.src).filter(Boolean),
        stylesheetUrls: [...doc.querySelectorAll('link[rel="stylesheet"]')].map(element => element.href) };
      if (surfaceKind === 'control') return result;
      const host = doc.querySelector('.publication-scene'), svg = host?.querySelector('svg');
      const metadata = JSON.parse(svg.querySelector('metadata')?.textContent ?? '{}');
      const visibleNodes = [...svg.querySelectorAll('[data-canonical-id][data-node-id]')].map(group => {
        const body = group.querySelector(':scope > rect[stroke-width]');
        const rect = plainRect(body?.getBoundingClientRect());
        const viewport = result.geometry.canvasViewport;
        return { nodeId: group.getAttribute('data-node-id'), canonicalId: group.getAttribute('data-canonical-id'), rect,
          intersectsCanvasViewport: !!(rect && viewport && rect.x + rect.width > viewport.x && rect.x < viewport.x + viewport.width && rect.y + rect.height > viewport.y && rect.y < viewport.y + viewport.height) };
      });
      return { ...result, documentId: svg.getAttribute('data-document-id'), revision: svg.getAttribute('data-revision'),
        sourceDigest: metadata.sourceDigest ?? null, irDigest: metadata.irDigest ?? null, metadata,
        expandedIds: JSON.parse(host.dataset.expandedIds ?? '[]'), pinnedIds: JSON.parse(host.dataset.pinnedIds ?? '[]'),
        visibleNodes, visibleNodeCount: visibleNodes.length, svgMarkup: svg.outerHTML };
    });
  }
  function environment() {
    const fontTargets = surfaceKind === 'control' ? [doc.getElementById('control-target')] : [doc.body, doc.querySelector('.publication-scene svg text')];
    return { utc: utc(), monotonicAt: clock(), timeOrigin: w.performance.timeOrigin, topTimeOrigin: topWindow.performance.timeOrigin,
      url: w.location.href, topUrl: topWindow.location.href, isIframe: w !== topWindow,
      userAgent: w.navigator.userAgent, platform: w.navigator.platform, languages: [...w.navigator.languages],
      hardwareConcurrency: w.navigator.hardwareConcurrency ?? null, deviceMemoryGiB: w.navigator.deviceMemory ?? null,
      viewport: { width: w.innerWidth, height: w.innerHeight, dpr: w.devicePixelRatio },
      topViewport: { width: topWindow.innerWidth, height: topWindow.innerHeight, dpr: topWindow.devicePixelRatio },
      screen: { width: w.screen.width, height: w.screen.height, availWidth: w.screen.availWidth, availHeight: w.screen.availHeight,
        colorDepth: w.screen.colorDepth, pixelDepth: w.screen.pixelDepth, orientation: w.screen.orientation?.type ?? null },
      crossOriginIsolated: w.crossOriginIsolated, reducedMotion: w.matchMedia('(prefers-reduced-motion: reduce)').matches,
      flags: flags(), fonts: { status: doc.fonts.status, faces: [...doc.fonts].map(face => ({ family: face.family, style: face.style, weight: face.weight, status: face.status })),
        declaredFamilies: fontTargets.filter(Boolean).map(target => ({ tag: target.tagName, family: w.getComputedStyle(target).fontFamily, size: w.getComputedStyle(target).fontSize })),
        resolvedGlyphBytesKnown: false },
      unknown: ['actual resolved glyph font bytes', 'external occlusion/visibility', 'display refresh and actual presentation', 'GPU model/clock', 'CPU/power lock', 'embed/headless scheduling policy'] };
  }
  function listen(target, type, fn) {
    target.addEventListener(type, fn, { capture: true, passive: true });
    listeners.push([target, type, fn]);
  }
  function environmental(event) {
    if (!running) return;
    timed('environment', () => {
      const record = { ...flags(event.type), eventTargetTag: event.target?.tagName ?? (event.target === w ? 'window' : null) };
      push('environmentChanges', record);
      if (['freeze', 'resume', 'pagehide', 'pageshow'].includes(event.type)) push('lifecycle', { ...record, persisted: event.persisted ?? null });
    }, { eventType: event.type });
  }
  function normalizedEventAt(timestamp, capturedAt) {
    return timestamp > capturedAt + 60000 ? timestamp - w.performance.timeOrigin : timestamp;
  }
  function input(event) {
    if (!running) return;
    timed('inputs', () => {
      const capturedAt = clock(), eventAt = normalizedEventAt(event.timeStamp, capturedAt);
      const raw = { id: `input-${++inputSequence}`, type: event.type, eventAt, capturedAt,
        eventPhase: phaseAt(eventAt), deliveryPhase: phaseAt(capturedAt), trusted: event.isTrusted, target: targetFacts(event.target),
        pointerId: event.pointerId ?? null, pointerType: event.pointerType ?? null,
        button: event.button ?? null, buttons: event.buttons ?? null, x: event.clientX ?? null, y: event.clientY ?? null,
        key: event.key ?? null, code: event.code ?? null, ctrl: !!event.ctrlKey, meta: !!event.metaKey, shift: !!event.shiftKey,
        deltaX: event.deltaX ?? null, deltaY: event.deltaY ?? null, deltaMode: event.deltaMode ?? null };
      if (event.type === 'pointermove' && typeof event.getCoalescedEvents === 'function') {
        raw.coalesced = event.getCoalescedEvents().map(coalesced => ({ eventAt: normalizedEventAt(coalesced.timeStamp, capturedAt), x: coalesced.clientX, y: coalesced.clientY }));
      }
      push('inputs', raw);
    }, { eventType: event.type });
  }
  function consume(type, entries, origin) {
    timed('performance', () => {
      for (const entry of entries) {
        const common = { observedAt: clock(), deliveryPhase: phaseAt(clock()), origin,
          startAt: entry.startTime, startPhase: phaseAt(entry.startTime), durationMs: entry.duration, name: entry.name };
        if (type === 'event') push('eventTiming', { ...common, processingStart: entry.processingStart, processingEnd: entry.processingEnd,
          interactionId: entry.interactionId ?? 0, target: targetFacts(entry.target) });
        else push('longTasks', { ...common, attribution: [...(entry.attribution ?? [])].map(item => ({ name: item.name, entryType: item.entryType,
          containerType: item.containerType, containerName: item.containerName, containerId: item.containerId, containerSrc: item.containerSrc })) });
      }
    }, { type, origin, entryCount: entries.length });
  }
  function observe(type) {
    if (!w.PerformanceObserver?.supportedEntryTypes?.includes(type)) return false;
    try {
      const observer = new w.PerformanceObserver(list => consume(type, list.getEntries(), 'callback'));
      observer.observe(type === 'event' ? { type, durationThreshold: 16, buffered: false } : { type, buffered: false });
      observers.push({ type, observer });
      return true;
    } catch (error) { fail(`observe-${type}`, error); return false; }
  }
  function drain(origin) {
    for (const { type, observer } of observers) {
      const beganAt = clock(), entries = observer.takeRecords();
      consume(type, entries, origin);
      push('drains', { origin, type, beganAt, endedAt: clock(), entryCount: entries.length });
    }
  }
  function frame(timestamp) {
    if (!running || phase !== 'capture') return;
    const beganAt = clock();
    try {
      const record = { timestamp, observedAt: clock(), timestampPhase: phaseAt(timestamp), deliveryPhase: phaseAt(clock()),
        visibility: doc.visibilityState, focused: doc.hasFocus(), topVisibility: topWindow.document.visibilityState,
        topFocused: topWindow.document.hasFocus(), geometry: mode === 'full' ? geometry() : null };
      record.observedAt = clock();
      push('frames', record);
    } catch (error) { fail('frame', error); }
    finally { push('overhead.frames', { at: beganAt, endAt: clock(), durationMs: clock() - beganAt, phase: phaseAt(beganAt) }); }
    rafId = w.requestAnimationFrame(frame);
  }
  function boundary(name, plannedAt = null) {
    const actualAt = clock();
    push('boundaries', { name, plannedAt, actualAt, latenessMs: plannedAt == null ? null : actualAt - plannedAt, utc: utc() });
    return actualAt;
  }
  function schedule(fn, deadline) { timers.push(w.setTimeout(fn, Math.max(0, deadline - clock()))); }
  function summarize() {
    const measuredInputs = data.inputs.filter(item => item.trusted && item.target.inMeasuredSurface && item.eventPhase === 'capture');
    const candidates = measuredInputs.filter(item => DISCRETE.has(item.type));
    const entries = data.eventTiming.filter(item => item.startPhase === 'capture' && item.target.inMeasuredSurface);
    const entryCandidates = entries.map(entry => candidates.filter(candidate => entry.name === candidate.type && entry.target.token !== null && entry.target.token === candidate.target.token && Math.abs(entry.startAt - candidate.eventAt) <= 2));
    const matches = candidates.map(candidate => {
      const indexes = entries.map((entry, index) => ({ entry, index })).filter(({ entry }) => entry.name === candidate.type && entry.target.token !== null && entry.target.token === candidate.target.token && Math.abs(entry.startAt - candidate.eventAt) <= 2);
      const unique = indexes.length === 1 && entryCandidates[indexes[0].index].length === 1;
      const entry = unique ? indexes[0].entry : null;
      const valid = !!entry && Number.isFinite(entry.durationMs) && entry.durationMs >= 0 && entry.processingStart >= entry.startAt && entry.processingEnd >= entry.processingStart;
      return { inputId: candidate.id, candidateEntryIndexes: indexes.map(item => item.index),
        status: indexes.length === 0 ? 'missing' : !unique ? 'ambiguous' : !valid ? 'invalid-entry' : 'matched',
        entryIndex: unique ? indexes[0].index : null, durationMs: valid ? entry.durationMs : null, interactionId: valid ? entry.interactionId : null };
    });
    const open = new Map(), gestures = [], orphanReleases = [];
    for (const item of measuredInputs) {
      if (item.type === 'pointerdown') {
        if (open.has(item.pointerId)) gestures.push({ down: open.get(item.pointerId), terminal: null, status: 'replaced-unclosed', nativeDurationMs: null });
        open.set(item.pointerId, item);
      } else if (item.type === 'pointerup' || item.type === 'pointercancel') {
        const down = open.get(item.pointerId);
        if (!down) orphanReleases.push(item.id);
        else {
          gestures.push({ downId: down.id, terminalId: item.id, pointerId: item.pointerId,
            downEventAt: down.eventAt, terminalEventAt: item.eventAt,
            nativeDurationMs: item.eventAt - down.eventAt, status: item.type === 'pointercancel' ? 'cancelled' : 'released',
            down: { x: down.x, y: down.y }, terminal: { x: item.x, y: item.y } });
          open.delete(item.pointerId);
        }
      }
    }
    for (const [pointerId, down] of open) gestures.push({ downId: down.id, pointerId, downEventAt: down.eventAt, terminalId: null, nativeDurationMs: null, status: 'unclosed-at-capture-end' });
    const lastInputAt = measuredInputs.length ? Math.max(...measuredInputs.map(item => item.eventAt)) : null;
    const by = (items, key) => items.reduce((counts, item) => { const value = key(item); counts[value] = (counts[value] ?? 0) + 1; return counts; }, {});
    const uniqueInteractions = items => [...new Set(items.map(item => item.interactionId).filter(id => id > 0))].sort((a, b) => a - b);
    data.gestures = { scope: 'trusted measured-surface inputs whose native timestamps are in capture', gestures, orphanReleaseIds: orphanReleases };
    data.denominators = { nativeMeasurementEnabled: mode === 'full', allRawInputs: data.inputs.length,
      rawByType: by(data.inputs, item => item.type), rawByEventPhase: by(data.inputs, item => item.eventPhase),
      rawByDeliveryPhase: by(data.inputs, item => item.deliveryPhase), rawByTrusted: by(data.inputs, item => String(item.trusted)),
      rawByMeasuredSurface: by(data.inputs, item => String(item.target.inMeasuredSurface)),
      trustedMeasuredInputsInCapture: mode === 'full' ? measuredInputs.length : null,
      discreteCandidatesInCapture: mode === 'full' ? candidates.length : null, matches,
      candidateMatchCounts: mode === 'full' ? by(matches, item => item.status) : null,
      allEventTimingEntries: data.eventTiming.length, eventTimingByDeliveryPhase: by(data.eventTiming, item => item.deliveryPhase),
      eventTimingByStartPhase: by(data.eventTiming, item => item.startPhase),
      eventTimingByMeasuredSurface: by(data.eventTiming, item => String(item.target.inMeasuredSurface)),
      eventTimingMeasuredCaptureEntries: entries.length, measuredCaptureEntryRawIndexes: entries.map(entry => data.eventTiming.indexOf(entry)),
      unmatchedMeasuredCaptureEntryIndexes: entries.map((entry, index) => index).filter(index => !matches.some(match => match.status === 'matched' && match.entryIndex === index)),
      allObservedPositiveInteractionIds: uniqueInteractions(data.eventTiming),
      matchedSubsetPositiveInteractionIds: uniqueInteractions(matches.filter(match => match.status === 'matched')),
      allLongTasks: data.longTasks.length, longTasksByStartPhase: by(data.longTasks, item => item.startPhase),
      lastMeasuredNativeInputAt: lastInputAt, postInputSettleBeforePlannedCaptureEndMs: lastInputAt == null ? null : data.deadlines.captureEnd - lastInputAt,
      allBufferAttempted: Object.values(data.buffers).reduce((sum, buffer) => sum + buffer.attempted, 0),
      allBufferDropped: Object.values(data.buffers).reduce((sum, buffer) => sum + buffer.dropped, 0), errors: data.errors.length };
    const transitionRecords = [data.environment.flags, ...data.environmentChanges, data.endEnvironment.flags];
    data.integrity = {
      anyHiddenRecord: transitionRecords.some(item => item.visibility !== 'visible' || item.topVisibility !== 'visible'),
      anyClippedSurfaceRecord: transitionRecords.some(item => !item.coverage.fullyInsideTopViewport),
      lifecycleFreezeOrPagehide: data.lifecycle.some(item => ['freeze', 'pagehide'].includes(item.eventType)),
      anyTopFocusFalseRecord: transitionRecords.some(item => !item.topFocused),
      lastInputCompletedByDeadline: mode === 'full' && lastInputAt != null ? lastInputAt <= data.deadlines.inputDeadline : null,
      atLeastTenSecondsPostInputSettle: mode === 'full' && lastInputAt != null ? data.deadlines.captureEnd - lastInputAt >= 10000 : null,
      trustedInputDuringDrain: data.inputs.some(item => item.trusted && item.eventPhase === 'drain'),
      unclosedGestures: gestures.filter(item => item.status.includes('unclosed')).length,
      operationHasMeasuredInput: mode === 'full' ? measuredInputs.length > 0 : null,
      expectedIdleHasMeasuredInput: mode === 'full' && operation === 'idle' ? measuredInputs.length > 0 : null,
      timerBoundaries: data.boundaries.filter(item => item.plannedAt != null),
      fixedWindowCompleted: data.status === 'fixed-window-complete',
      continuousForegroundExternallyCertified: false, presentedResponseCertified: false,
      instruction: 'Retain confounded/no-input/late/cancelled windows. These flags are observations, not an automatic performance pass.' };
  }
  function finish(reason) {
    if (!running) return;
    boundary(reason, reason === 'fixed-window-complete' ? data.deadlines.drainEnd : null);
    drain(reason === 'fixed-window-complete' ? 'final-fixed-drain' : 'cancel-drain');
    running = false;
    w.cancelAnimationFrame(rafId);
    for (const timer of timers) w.clearTimeout(timer);
    for (const [target, type, fn] of listeners) target.removeEventListener(type, fn, true);
    for (const { observer } of observers) observer.disconnect();
    phase = 'disconnected';
    data.status = reason;
    data.disconnectedAt = clock();
    data.disconnectedUtc = utc();
    try { data.bindingAfter = publicSnapshot(); } catch (error) { fail('final-snapshot', error); }
    data.endEnvironment = environment();
    summarize();
    onComplete(data);
  }
  function beginCapture() {
    if (!running) return;
    boundary('warmup-end', data.deadlines.warmupEnd);
    try { data.bindingBefore = publicSnapshot(); }
    catch (error) { fail('initial-snapshot', error); finish('initial-snapshot-failed'); return; }
    // Large initial snapshot occurs before the predetermined timed capture.
    const began = clock();
    data.deadlines.captureStart = began;
    data.deadlines.inputDeadline = began + INPUT_DEADLINE_MS;
    data.deadlines.captureEnd = began + CAPTURE_MS;
    data.deadlines.drainEnd = began + CAPTURE_MS + DRAIN_MS;
    boundary('capture-start', began);
    phase = 'capture';
    if (mode === 'full') {
      data.supported.eventTimingObserved = observe('event');
      data.supported.longTasksObserved = observe('longtask');
      for (const type of INPUT_TYPES) listen(w, type, input);
    }
    rafId = w.requestAnimationFrame(frame);
    schedule(() => {
      if (!running) return;
      boundary('capture-end', data.deadlines.captureEnd);
      phase = 'drain';
      w.cancelAnimationFrame(rafId);
      drain('capture-fixed-drain');
      onPhase('drain');
    }, data.deadlines.captureEnd);
    schedule(() => finish('fixed-window-complete'), data.deadlines.drainEnd);
    onPhase('capture');
  }
  return {
    start() {
      if (used) throw new Error('A new observer is required for each attempted session');
      used = true;
      if (!measuredSurfaceCoverage(topWindow, surface).fullyInsideTopViewport) throw new Error('Measurement surface is clipped');
      running = true;
      phase = 'warmup';
      data.status = 'running';
      data.environment = environment();
      data.supported.eventTimingAvailable = w.PerformanceObserver?.supportedEntryTypes?.includes('event') ?? false;
      data.supported.longTasksAvailable = w.PerformanceObserver?.supportedEntryTypes?.includes('longtask') ?? false;
      const began = boundary('warmup-start');
      data.deadlines.warmupStart = began;
      data.deadlines.warmupEnd = began + WARMUP_MS;
      for (const type of ['visibilitychange', 'freeze', 'resume']) listen(doc, type, environmental);
      for (const type of ['focus', 'blur', 'pagehide', 'pageshow', 'resize', 'scroll']) listen(w, type, environmental);
      if (w !== topWindow) {
        listen(topWindow.document, 'visibilitychange', environmental);
        for (const type of ['focus', 'blur', 'resize', 'scroll', 'pagehide', 'pageshow']) listen(topWindow, type, environmental);
      }
      schedule(beginCapture, data.deadlines.warmupEnd);
      onPhase('warmup');
      return { warmupStart: began, plannedWarmupEnd: data.deadlines.warmupEnd };
    },
    cancel(reason = 'cancelled') { if (running) finish(`cancelled:${reason}`); }
  };
}
