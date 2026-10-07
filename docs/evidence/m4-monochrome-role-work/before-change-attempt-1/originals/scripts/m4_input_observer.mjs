/** Independent opt-in DOM observer. No Studio imports, dispatch, or hidden state. */
const OPERATIONS = new Set(['drag', 'pan', 'zoom', 'undo', 'redo', 'toggle', 'pin']);
const INPUT_TYPES = ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'lostpointercapture', 'click', 'keydown', 'keyup', 'wheel', 'blur'];
const LIMIT = 10_000;
const plainMatrix = m => m && Object.fromEntries(['a', 'b', 'c', 'd', 'e', 'f'].map(k => [k, m[k]]));
const plainRect = r => r && { x: r.x, y: r.y, width: r.width, height: r.height };

export function createInputObserver(studioWindow, { mode = 'full', onProgress = () => {} } = {}) {
  if (!['full', 'raf-only'].includes(mode)) throw new Error('mode must be full or raf-only');
  const w = studioWindow, doc = w.document, clock = () => w.performance.now();
  // Accessing document enforces same origin. No product window globals are read.
  if (!doc?.querySelector) throw new Error('A same-origin Studio window is required');
  const targetTokens = new WeakMap(); let tokenSequence = 0, inputSequence = 0;
  const data = {
    schemaVersion: 2, protocol: 'archcanvas-input-observation/2', label: '',
    measurement: { mode, runtimeAccess: 'DOM-only', coordinateSpace: 'window-client-css-pixels',
      latency: 'matched-discrete-event-timing-only', continuousInput: 'observed-geometry-proxy-not-paint',
      frames: 'raf-callback-cadence-not-presented-frames', durationThresholdMs: 16, durationQuantizationMs: 8,
      panTrigger: 'public-tool-space-middle/1', panTerminal: 'same-pointer-up-and-viewport-relative-camera/1',
      documentContinuity: 'public-svg-and-frontier-not-hidden-document/1' },
    environment: null, startedAt: null, stoppedAt: null, bindingAtStart: null,
    trials: [], events: [], frames: [], eventTiming: [], longTasks: [], visibility: [],
    overhead: { sceneReads: [], inputCallbacks: [], frameCallbacks: [], performanceCallbacks: [] },
    buffers: {}, errors: [],
    limitations: ['Event Timing does not cover pointermove or wheel; missing/ambiguous entries stay unmeasured.',
      'Observed DOM geometry and rAF callbacks do not prove a presented frame or continuous input-to-paint.',
      'Trusted automation is not a human participant; iframe timing is a distinct environment.',
      'Self-cost covers this observer only; existing Studio telemetry, renderer and system CPU are not isolated.',
      'Font-loading state does not bind actual fallback font bytes.',
      'Matching public SVG/frontier/selection markup does not prove hidden CanvasDocument or history equality.',
      'Terminal camera matching proves recorded committed DOM coordinates, not causal presented paint.']
  };
  let running = false, used = false, rafId = 0, current = null, spaceHeld = false;
  const observers = [], listeners = [];
  function push(path, value, limit = LIMIT) {
    const parts = path.split('.'); let list = data;
    for (const part of parts) list = list[part];
    const buffer = data.buffers[path] ??= { limit, dropped: 0 };
    if (list.length < limit) list.push(value); else buffer.dropped++;
  }
  function token(target) {
    if (!(target instanceof w.Element)) return null;
    if (!targetTokens.has(target)) targetTokens.set(target, `target-${++tokenSequence}`);
    return targetTokens.get(target);
  }
  function publicTool() {
    const canvasTool = doc.querySelector('.canvas-viewport')?.getAttribute('data-canvas-tool') ?? null;
    const pressed = doc.querySelector('.canvas-toolbar button[aria-label="平移画布"]')?.getAttribute('aria-pressed');
    return { canvasTool, handToolPressed: pressed === 'true' ? true : pressed === 'false' ? false : null };
  }
  function targetFacts(target) {
    const tool = publicTool();
    if (!(target instanceof w.Element)) return { token: null, nodeId: null, kind: 'other', action: null, ...tool,
      inCanvas: false, editingTarget: false, canvasControl: false };
    const button = target.closest('button'), label = button?.getAttribute('aria-label') ?? button?.getAttribute('title') ?? '';
    let action = null;
    if (button?.closest('.zoom-control') || label === '适合画布 F') action = 'zoom';
    else if (label === '撤销 Ctrl+Z') action = 'undo';
    else if (label === '重做 Ctrl+Shift+Z') action = 'redo';
    else if (label === '固定 / 解锁') action = 'pin';
    const expand = target.closest('[data-expand-id]'), tree = target.closest('[data-tree-node-id]');
    const body = target.closest('[data-canonical-id]');
    const nodeId = expand?.getAttribute('data-expand-id') ?? tree?.getAttribute('data-tree-node-id') ?? body?.getAttribute('data-node-id') ?? null;
    const kind = expand || target.closest('.tree-toggle') ? 'toggle' : target.closest('[data-port-id]') ? 'port' : body ? 'node' : target.closest('.canvas-viewport') ? 'viewport' : 'other';
    return { token: token(target), nodeId, kind, action, label, ...tool,
      inCanvas: !!target.closest('.canvas-viewport'), editingTarget: !!target.closest('input,textarea,select,[contenteditable]'),
      canvasControl: !!target.closest('button') };
  }
  function inputFacts(event) {
    const capturedAt = clock();
    const eventAt = event.timeStamp > capturedAt + 60_000 ? event.timeStamp - w.performance.timeOrigin : event.timeStamp;
    const raw = { id: `input-${++inputSequence}`, type: event.type, eventAt, capturedAt,
      trusted: event.isTrusted, target: targetFacts(event.target), pointerId: event.pointerId ?? null,
      pointerType: event.pointerType ?? null, button: event.button ?? null, buttons: event.buttons ?? null,
      x: event.clientX ?? null, y: event.clientY ?? null, key: event.key ?? null, code: event.code ?? null,
      ctrl: !!event.ctrlKey, meta: !!event.metaKey, shift: !!event.shiftKey, spaceHeld,
      deltaX: event.deltaX ?? null, deltaY: event.deltaY ?? null, deltaMode: event.deltaMode ?? null,
      viewport: plainRect(doc.querySelector('.canvas-viewport')?.getBoundingClientRect()) };
    if (event.type === 'pointermove' && typeof event.getCoalescedEvents === 'function') {
      raw.coalesced = event.getCoalescedEvents().map(e => ({ at: e.timeStamp > capturedAt + 60_000 ? e.timeStamp - w.performance.timeOrigin : e.timeStamp, x: e.clientX, y: e.clientY }));
    }
    return raw;
  }
  function panTrigger(raw) {
    return raw.type === 'pointerdown' && raw.target.inCanvas && !raw.target.editingTarget && !raw.target.canvasControl &&
      (raw.button === 1 || raw.button === 0 && (raw.spaceHeld || raw.target.canvasTool === 'pan' && raw.target.handToolPressed === true));
  }
  function starts(spec, raw) {
    if (!raw.trusted) return false;
    const pointer = raw.type === 'pointerdown', keyboard = raw.type === 'keydown';
    const chosen = !spec.targetIds.length || spec.targetIds.includes(raw.target.nodeId);
    switch (spec.operation) {
      case 'drag': return pointer && raw.button === 0 && raw.target.kind === 'node' && chosen && !panTrigger(raw);
      case 'pan': return panTrigger(raw);
      case 'zoom': return pointer && raw.target.action === 'zoom' || raw.type === 'wheel' && raw.target.kind !== 'other' || keyboard && raw.key?.toLowerCase() === 'f';
      case 'undo': case 'redo': return pointer && raw.target.action === spec.operation || keyboard && (raw.ctrl || raw.meta) && raw.key?.toLowerCase() === 'z' && raw.shift === (spec.operation === 'redo');
      case 'pin': return pointer && raw.target.action === 'pin';
      case 'toggle': return pointer && raw.target.kind === 'toggle' && chosen;
      default: return false;
    }
  }
  function geometry(spec, full) {
    const began = clock();
    try {
      const host = doc.querySelector('.publication-scene'), svg = host?.querySelector('svg'), paper = doc.querySelector('.paper');
      if (!svg || !paper) throw new Error('No rendered Studio SVG');
      const cssTransform = w.getComputedStyle(paper).transform;
      const matrix = plainMatrix(new w.DOMMatrixReadOnly(cssTransform === 'none' ? undefined : cssTransform));
      const viewport = plainRect(doc.querySelector('.canvas-viewport')?.getBoundingClientRect());
      const result = { at: clock(), documentId: svg.getAttribute('data-document-id'), revision: Number(svg.getAttribute('data-revision')),
        camera: { cssTransform, matrix }, viewport, frameRect: plainRect(w.frameElement?.getBoundingClientRect()), objects: {}, ...publicTool() };
      const ids = [...new Set([...(spec?.targetIds ?? []), ...(spec?.anchorIds ?? []), ...(spec?.pinnedIds ?? [])])];
      for (const id of ids) {
        const group = svg.querySelector(`[data-canonical-id][data-node-id="${w.CSS.escape(id)}"]`);
        const body = group?.querySelector(':scope > rect[stroke-width]'), ctm = body?.getScreenCTM();
        if (!body || !ctm) { result.objects[id] = null; continue; }
        const canvas = { x: body.x.baseVal.value, y: body.y.baseVal.value, width: body.width.baseVal.value, height: body.height.baseVal.value };
        const corners = [[canvas.x, canvas.y], [canvas.x + canvas.width, canvas.y], [canvas.x, canvas.y + canvas.height], [canvas.x + canvas.width, canvas.y + canvas.height]]
          .map(([x, y]) => new w.DOMPoint(x, y).matrixTransform(ctm));
        const x = Math.min(...corners.map(p => p.x)), y = Math.min(...corners.map(p => p.y));
        const screen = { x, y, width: Math.max(...corners.map(p => p.x)) - x, height: Math.max(...corners.map(p => p.y)) - y };
        const intersectsViewport = !!viewport && screen.x + screen.width > viewport.x && screen.x < viewport.x + viewport.width && screen.y + screen.height > viewport.y && screen.y < viewport.y + viewport.height;
        result.objects[id] = { canvas, screen, screenMatrix: plainMatrix(ctm), intersectsViewport, label: group.getAttribute('aria-label'), canonicalId: group.getAttribute('data-canonical-id') };
      }
      if (full) {
        const metadata = JSON.parse(svg.querySelector('metadata')?.textContent ?? '{}');
        Object.assign(result, { sourceDigest: metadata.sourceDigest, irDigest: metadata.irDigest,
          visibleIds: [...svg.querySelectorAll('[data-canonical-id]')].map(e => e.getAttribute('data-node-id')).sort(),
          expandedIds: JSON.parse(host.dataset.expandedIds ?? '[]'), pinnedIds: JSON.parse(host.dataset.pinnedIds ?? '[]'),
          svgMarkup: svg.outerHTML,
          selectionMarkup: [...doc.querySelectorAll('.paper .selection-outline')].map(element => element.outerHTML) });
      }
      result.at = clock();
      return result;
    } finally { push('overhead.sceneReads', { at: began, durationMs: clock() - began, full }); }
  }
  function progress() { onProgress({ trials: data.trials.length, activeTrialId: current?.id ?? null, inputs: data.events.length, frames: data.frames.length }); }
  function capture(event) {
    if (!running) return;
    // Window blur cancels navigation; a descendant input/button blur is only
    // focus movement inside the Studio and must not cancel the active trial.
    if (event.type === 'blur' && event.target !== w) return;
    const began = clock();
    try {
      if (event.type === 'keydown' && event.code === 'Space' &&
        (!(event.target instanceof w.Element) || !event.target.closest('input,textarea,select,[contenteditable]'))) spaceHeld = true;
      if (event.type === 'keyup' && event.code === 'Space') spaceHeld = false;
      if (event.type === 'blur') spaceHeld = false;
      const raw = inputFacts(event);
      if (current?.status === 'armed' && starts(current.spec, raw)) {
        current.before = geometry(current.spec, true); current.status = 'observing'; current.firstEventId = raw.id;
      }
      raw.trialId = current?.status === 'observing' ? current.id : null;
      push('events', raw);
      if (raw.trialId) current.lastEventId = raw.id;
      progress();
    } catch (error) { push('errors', { at: clock(), phase: 'input', error: String(error) }, 100); }
    finally { push('overhead.inputCallbacks', { at: began, durationMs: clock() - began, type: event.type }); }
  }
  function frame(at) {
    if (!running) return;
    const began = clock();
    try {
      const record = { at, observedAt: clock(), trialId: current?.status === 'observing' ? current.id : null, geometry: null };
      if (record.trialId) record.geometry = geometry(current.spec, false);
      record.observedAt = clock(); push('frames', record);
    } catch (error) { push('errors', { at: clock(), phase: 'frame', error: String(error) }, 100); }
    finally { push('overhead.frameCallbacks', { at: began, durationMs: clock() - began }); }
    rafId = w.requestAnimationFrame(frame);
  }
  function visibility() { push('visibility', { at: clock(), state: doc.visibilityState, hasFocus: doc.hasFocus(), topHasFocus: w.parent.document.hasFocus() }); }
  function listen(target, type, callback) { target.addEventListener(type, callback, { capture: true, passive: true }); listeners.push([target, type, callback]); }
  function observe(type, callback) {
    if (!w.PerformanceObserver?.supportedEntryTypes?.includes(type)) return false;
    try {
      const observer = new w.PerformanceObserver(list => {
        const began = clock();
        try { callback(list.getEntries()); }
        finally { push('overhead.performanceCallbacks', { at: began, durationMs: clock() - began, type }); }
      });
      observer.observe(type === 'event' ? { type, durationThreshold: 16 } : { entryTypes: [type] }); observers.push(observer); return true;
    } catch (error) { push('errors', { at: clock(), phase: `observe-${type}`, error: String(error) }, 100); return false; }
  }
  function eventEntries(entries) {
    for (const e of entries) push('eventTiming', { name: e.name, startAt: e.startTime, durationMs: e.duration,
      processingStart: e.processingStart, processingEnd: e.processingEnd, interactionId: e.interactionId ?? 0,
      targetToken: token(e.target), targetNodeId: targetFacts(e.target).nodeId }, 5000);
  }
  function longEntries(entries) { for (const e of entries) push('longTasks', { at: e.startTime, durationMs: e.duration, name: e.name,
    attribution: (e.attribution ?? []).map(a => ({ name: a.name, containerType: a.containerType, containerName: a.containerName, containerSrc: a.containerSrc })) }, 5000); }
  function finishTrial(status = 'finished') {
    if (!running || !current) throw new Error('No armed trial');
    current.after = geometry(current.spec, true); current.finishedAt = clock();
    current.status = current.status === 'armed' ? 'no-input' : status;
    const result = current; current = null; progress(); return result;
  }
  return {
    start({ label = '' } = {}) {
      if (used) throw new Error('Create a new observer for each session'); used = true; running = true;
      data.label = label; data.startedAt = clock();
      data.bindingAtStart = geometry(null, true);
      const supported = { eventTimingAvailable: w.PerformanceObserver?.supportedEntryTypes?.includes('event') ?? false,
        longTasksAvailable: w.PerformanceObserver?.supportedEntryTypes?.includes('longtask') ?? false,
        eventTimingObserved: false, longTasksObserved: false };
      if (mode === 'full') {
        supported.eventTimingObserved = observe('event', eventEntries); supported.longTasksObserved = observe('longtask', longEntries);
        for (const type of INPUT_TYPES) listen(w, type, capture);
      }
      data.environment = { url: w.location.href, topUrl: w.parent.location.href, timeOrigin: w.performance.timeOrigin,
        userAgent: w.navigator.userAgent, viewport: { width: w.innerWidth, height: w.innerHeight, devicePixelRatio: w.devicePixelRatio },
        scripts: [...doc.scripts].map(s => s.src).filter(Boolean), isIframe: w !== w.parent, supported,
        fonts: { status: doc.fonts.status, loadedFaces: [...doc.fonts].map(f => ({ family: f.family, status: f.status })) } };
      listen(doc, 'visibilitychange', visibility); listen(w, 'focus', visibility); listen(w, 'blur', visibility); visibility();
      rafId = w.requestAnimationFrame(frame); progress(); return { startedAt: data.startedAt };
    },
    arm({ operation, targetIds = [], anchorIds = [], pinnedIds = [] }) {
      if (!running || mode !== 'full') throw new Error('Start a full session before arming');
      if (current) throw new Error('Finish the previous trial first');
      if (!OPERATIONS.has(operation) || ![targetIds, anchorIds, pinnedIds].every(ids => Array.isArray(ids) && ids.every(id => typeof id === 'string')) || ['drag', 'toggle'].includes(operation) && !targetIds.length) throw new Error('Invalid operation or selected IDs');
      if (data.trials.length >= 100) throw new Error('Trial limit reached');
      current = { id: `trial-${data.trials.length + 1}`, spec: { operation, targetIds: [...targetIds], anchorIds: [...anchorIds], pinnedIds: [...pinnedIds] },
        armedAt: clock(), status: 'armed', before: null, after: null, firstEventId: null, lastEventId: null, finishedAt: null };
      data.trials.push(current); progress(); return current.id;
    },
    finishTrial,
    stop() {
      if (!running) throw new Error('Observer is not running');
      if (current) finishTrial('stopped-pending');
      visibility(); running = false; w.cancelAnimationFrame(rafId);
      for (const [target, type, callback] of listeners) target.removeEventListener(type, callback, true);
      // Drain queued entries instead of silently losing the final native input.
      for (const observer of observers) {
        const entries = observer.takeRecords();
        if (entries.length) entries[0].entryType === 'event' ? eventEntries(entries) : longEntries(entries);
        observer.disconnect();
      }
      data.stoppedAt = clock(); return structuredClone(data);
    }
  };
}
