import type { Bounds, CanvasDocument, MoveScope, Scene, SceneBuildOptions, SceneDiagnostic, VisualOperation } from './types.ts';
import { resolveMoveScope } from './document.ts';
import { buildScene } from './scene.ts';
import { prepareMovePreview, previewMoveScene } from './movePreview.ts';
import { TOKENS } from './tokens.ts';
import { validateDocument } from './validate.ts';
import { orthogonalPathPoints } from './orthogonalRouter.ts';
import { routeLaneConflicts } from './routeLaneConflicts.ts';
import { edgeLabelBounds } from './edgeLabelPlacement.ts';
import { nodeVisualOutline } from './nodeVisualOutline.ts';
import { implicitRootIds } from './containerPresentation.ts';

type Move = Extract<VisualOperation, { type: 'move' }>;
export type LayoutRecoveryPlan =
  | { status: 'unneeded' | 'unavailable'; reason: string }
  | { status: 'ready'; id: string; operation: Move; scene: Scene; candidateCount: number };
export const LAYOUT_RECOVERY_CANDIDATE_LIMIT = 64;

function descendants(document: CanvasDocument, id: string): Set<string> {
  const byId = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const ids = new Set<string>(), queue = [id];
  while (queue.length) {
    const current = queue.pop()!;
    if (ids.has(current)) continue;
    ids.add(current); queue.push(...byId.get(current)?.children ?? []);
  }
  return ids;
}
function signature(diagnostic: SceneDiagnostic): string {
  return JSON.stringify([diagnostic.code, diagnostic.objectIds, diagnostic.edgeId,
    diagnostic.relatedEdgeIds && [...diagnostic.relatedEdgeIds].sort()]);
}
function conflicts(scene: Scene, moving: Set<string>): SceneDiagnostic[] {
  const incidentEdges = new Set(scene.edges.filter(edge => moving.has(edge.sourceId) || moving.has(edge.targetId)).map(edge => edge.id));
  return scene.diagnostics.filter(diagnostic => diagnostic.code &&
    (diagnostic.objectIds?.some(id => moving.has(id)) || (diagnostic.edgeId && incidentEdges.has(diagnostic.edgeId)) ||
      diagnostic.relatedEdgeIds?.some(id => incidentEdges.has(id))));
}
const retainedRouteWarning = (diagnostic: SceneDiagnostic) =>
  diagnostic.code === 'layout-route-blocked' || diagnostic.code === 'layout-route-overlap';
const area = (a: Bounds, b: Bounds) =>
  Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) *
  Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
function unionIntersectionArea(first: readonly Bounds[], second: readonly Bounds[]): number {
  const intersections = first.flatMap(a => second.flatMap(b => area(a, b) > 0
    ? [{ x: Math.max(a.x, b.x), y: Math.max(a.y, b.y),
      width: Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x),
      height: Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) }] : []));
  const xs = [...new Set(intersections.flatMap(body => [body.x, body.x + body.width]))].sort((a, b) => a - b);
  let result = 0;
  for (let i = 1; i < xs.length; i++) {
    const intervals = intersections.filter(body => body.x < xs[i] && body.x + body.width > xs[i - 1])
      .map(body => [body.y, body.y + body.height] as [number, number]).sort((a, b) => a[0] - b[0]);
    const merged: [number, number][] = [];
    for (const interval of intervals) {
      const last = merged.at(-1);
      if (last && interval[0] <= last[1]) last[1] = Math.max(last[1], interval[1]);
      else merged.push([...interval]);
    }
    result += (xs[i] - xs[i - 1]) * merged.reduce((sum, [low, high]) => sum + high - low, 0);
  }
  return result;
}
function insideLength(path: string, bodies: readonly Bounds[]): number {
  const points = orthogonalPathPoints(path);
  let result = 0;
  for (let index = 1; index < points.length; index++) {
    const a = points[index - 1], b = points[index], dx = b.x - a.x, dy = b.y - a.y;
    const intervals: [number, number][] = [];
    for (const body of bodies) {
      let low = 0, high = 1;
      for (const [origin, delta, min, max] of [[a.x, dx, body.x, body.x + body.width], [a.y, dy, body.y, body.y + body.height]]) {
        if (Math.abs(delta) < 1e-6) { if (origin <= min || origin >= max) high = 0; }
        else { const p = (min - origin) / delta, q = (max - origin) / delta; low = Math.max(low, Math.min(p, q)); high = Math.min(high, Math.max(p, q)); }
      }
      if (high > low) intervals.push([low, high]);
    }
    const merged: [number, number][] = [];
    for (const interval of intervals.sort((p, q) => p[0] - q[0])) {
      const last = merged.at(-1);
      if (last && interval[0] <= last[1]) last[1] = Math.max(last[1], interval[1]);
      else merged.push([...interval]);
    }
    result += merged.reduce((sum, [low, high]) => sum + high - low, 0) * Math.hypot(dx, dy);
  }
  return result;
}
function captionMetrics(scene: Scene, diagnostic: SceneDiagnostic, unframedIds: ReadonlySet<string>): Map<string, number> {
  const edge = scene.edges.find(item => item.id === diagnostic.edgeId), metrics = new Map<string, number>();
  if (!edge?.label) return metrics;
  const caption = edgeLabelBounds(edge.label, edge.labelX, edge.labelY);
  // Compare each peer separately: a caption losing one blocker must not be
  // allowed to penetrate another body or unrelated route more deeply.
  for (const node of scene.nodes.filter(node => !unframedIds.has(node.id))) metrics.set(`node:${node.id}`, unionIntersectionArea([caption], node.expanded
    ? [{ ...node, height: node.headerHeight }] : nodeVisualOutline(node).rectangles));
  for (const annotation of scene.annotations) metrics.set(`annotation:${annotation.id}`, area(caption, annotation));
  for (const other of scene.edges) if (other.id !== edge.id) {
    if (other.label) metrics.set(`caption:${other.id}`, area(caption, edgeLabelBounds(other.label, other.labelX, other.labelY)));
    metrics.set(`route:${other.id}`, insideLength(other.path, [caption]));
  }
  for (const guide of scene.captionGuides ?? []) if (guide.sceneEdgeId !== edge.id) metrics.set(`guide:${guide.id}`, insideLength(guide.path, [caption]));
  const points = orthogonalPathPoints(edge.path);
  const distance = Math.min(...points.slice(1).map((b, index) => {
    const a = points[index];
    return Math.hypot(Math.max(caption.x - Math.max(a.x, b.x), Math.min(a.x, b.x) - caption.x - caption.width, 0),
      Math.max(caption.y - Math.max(a.y, b.y), Math.min(a.y, b.y) - caption.y - caption.height, 0));
  }));
  metrics.set('association-distance', distance);
  return metrics;
}
function blockedMetrics(scene: Scene, diagnostic: SceneDiagnostic): Map<string, number> {
  const edge = scene.edges.find(item => item.id === diagnostic.edgeId), result = new Map<string, number>();
  if (!edge) return result;
  const byId = new Map(scene.nodes.map(node => [node.id, node]));
  const ancestor = (id: string, child: string) => {
    let parent = byId.get(child)?.parentId;
    while (parent) { if (parent === id) return true; parent = byId.get(parent)?.parentId; }
    return false;
  };
  for (const id of diagnostic.objectIds ?? []) {
    const body = byId.get(id); if (!body) continue;
    result.set(id, insideLength(edge.path, ancestor(id, edge.sourceId) || ancestor(id, edge.targetId)
      ? [{ ...body, height: body.headerHeight + 4 }] : nodeVisualOutline(body).rectangles));
  }
  return result;
}
function severity(scene: Scene, diagnostic: SceneDiagnostic): number {
  const byId = new Map(scene.nodes.map(node => [node.id, node]));
  const [first, second] = (diagnostic.objectIds ?? []).map(id => byId.get(id));
  if (first && second && diagnostic.code === 'layout-overlap') return unionIntersectionArea(nodeVisualOutline(first).rectangles, nodeVisualOutline(second).rectangles);
  if (first && second && diagnostic.code === 'layout-header-overlap') return unionIntersectionArea(nodeVisualOutline(first).rectangles, [{ ...second, height: second.headerHeight }]);
  if (first && second && diagnostic.code === 'layout-outside-parent') {
    const bounds = nodeVisualOutline(first).bounds;
    return Math.max(0, second.x - bounds.x) + Math.max(0, second.y - bounds.y) +
      Math.max(0, bounds.x + bounds.width - second.x - second.width) + Math.max(0, bounds.y + bounds.height - second.y - second.height);
  }
  if (diagnostic.code === 'layout-route-overlap') {
    // Measure final ambiguous spans, including role/style/canonical fan-out
    // exemptions. The same primary edge can overlap several different peers.
    const ids = new Set((diagnostic.relatedEdgeIds ?? [diagnostic.edgeId]).filter((id): id is string => !!id));
    const lanes = routeLaneConflicts(scene.edges);
    return lanes.filter(conflict => ids.has(conflict.firstId) || ids.has(conflict.secondId))
      .reduce((sum, conflict) => sum + conflict.length, 0);
  }
  if (diagnostic.code !== 'layout-route-blocked') return 0;
  return [...blockedMetrics(scene, diagnostic).values()].reduce((sum, value) => sum + value, 0);
}

/** An explicit proposal, never an implicit clamp or a change to source facts. */
export function planLayoutRecovery(document: CanvasDocument, id: string, scope?: MoveScope, options: SceneBuildOptions = {}): LayoutRecoveryPlan {
  validateDocument(document);
  const moveScope = resolveMoveScope(scope);
  const original = buildScene(document, options), selected = original.nodes.find(node => node.id === id);
  const unframedIds = options.presentation === 'editor' ? implicitRootIds(original) : new Set<string>();
  if (!selected) return { status: 'unavailable', reason: '请先选择一个当前可见的对象。' };
  const moving = descendants(document, id);
  if (document.pinnedObjects.some(pin => moving.has(pin))) return { status: 'unavailable', reason: '选中对象或其内部对象已固定。取消固定后再预览位置修复。' };
  const selectedConflicts = conflicts(original, moving);
  if (!selectedConflicts.length) return { status: 'unneeded', reason: '这个对象没有需要修复的布局冲突。' };
  if (selectedConflicts.some(diagnostic => !retainedRouteWarning(diagnostic) && (diagnostic.objectIds?.length ?? 0) >= 2 && diagnostic.objectIds!.every(item => moving.has(item)))) {
    return { status: 'unavailable', reason: '冲突发生在选中容器内部。请先选择越界或重叠的内部对象，再预览位置修复。' };
  }

  const byId = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const ancestors = new Set<string>();
  let parentId = byId.get(id)?.parentId;
  while (parentId) { ancestors.add(parentId); parentId = byId.get(parentId)?.parentId; }
  const parent = original.nodes.find(node => node.id === selected.parentId && !unframedIds.has(node.id));
  const left = parent?.expanded ? parent.x + TOKENS.padding : Number.NEGATIVE_INFINITY;
  const top = parent?.expanded ? parent.y + parent.headerHeight + 16 : Number.NEGATIVE_INFINITY;
  const obstacles = original.nodes.filter(node => !moving.has(node.id) && !ancestors.has(node.id) && !unframedIds.has(node.id));
  const positions = new Map<string, { x: number; y: number }>();
  const add = (x: number, y: number) => {
    x = Math.max(left, x); y = Math.max(top, y);
    const dx = x - selected.x, dy = y - selected.y;
    if (!Number.isFinite(x) || !Number.isFinite(y) || (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6)) return;
    positions.set(`${x}:${y}`, { x, y });
  };
  // First restore containment/title clearance; then consider nearby obstacle sides.
  add(selected.x, selected.y);
  const near = [...obstacles].sort((a, b) =>
    Math.abs(a.x - selected.x) + Math.abs(a.y - selected.y) - Math.abs(b.x - selected.x) - Math.abs(b.y - selected.y)).slice(0, 16);
  const xs = [selected.x, Math.max(left, selected.x)], ys = [selected.y, Math.max(top, selected.y)];
  for (const obstacle of near) {
    const beforeX = obstacle.x - selected.width - TOKENS.gapX, afterX = obstacle.x + obstacle.width + TOKENS.gapX;
    const beforeY = obstacle.y - selected.height - TOKENS.gapY, afterY = obstacle.y + obstacle.height + TOKENS.gapY;
    xs.push(beforeX, afterX); ys.push(beforeY, afterY);
    add(beforeX, selected.y); add(afterX, selected.y); add(selected.x, beforeY); add(selected.x, afterY);
  }
  for (const x of xs) for (const y of ys) add(x, y);
  const candidates = [...positions.values()].sort((a, b) =>
    Math.abs(a.x - selected.x) + Math.abs(a.y - selected.y) - Math.abs(b.x - selected.x) - Math.abs(b.y - selected.y) || a.y - b.y || a.x - b.x).slice(0, LAYOUT_RECOVERY_CANDIDATE_LIMIT);
  const existing = new Map(original.diagnostics.filter(diagnostic => diagnostic.code).map(diagnostic => [signature(diagnostic), severity(original, diagnostic)]));
  const captions = new Map(original.diagnostics.filter(diagnostic => diagnostic.code?.startsWith('layout-edge-label-'))
    .map(diagnostic => [signature(diagnostic), captionMetrics(original, diagnostic, unframedIds)]));
  const blocked = new Map(original.diagnostics.filter(diagnostic => diagnostic.code === 'layout-route-blocked')
    .map(diagnostic => [signature(diagnostic), blockedMetrics(original, diagnostic)]));
  const session = prepareMovePreview(document, [id], moveScope);
  let candidateCount = 0;
  for (const position of candidates) {
    candidateCount++;
    const dx = position.x - selected.x, dy = position.y - selected.y;
    const scene = previewMoveScene(session, dx, dy, options);
    const selectedDiagnostics = conflicts(scene, moving);
    const worsened = (diagnostic: SceneDiagnostic) => diagnostic.code &&
      (!existing.has(signature(diagnostic)) || severity(scene, diagnostic) > existing.get(signature(diagnostic))! + 1e-6 ||
        (diagnostic.code === 'layout-route-blocked' && [...blockedMetrics(scene, diagnostic)].some(([peer, value]) =>
          value > (blocked.get(signature(diagnostic))?.get(peer) ?? 0) + 1e-6)) ||
        (diagnostic.code.startsWith('layout-edge-label-') && [...captionMetrics(scene, diagnostic, unframedIds)].some(([peer, value]) =>
          value > (captions.get(signature(diagnostic))?.get(peer) ?? 0) + 1e-6)));
    // A position repair must actually clear every selected body/header/parent
    // conflict. Existing route warnings may survive only without new peers or
    // increased obstruction/ambiguous-lane length; they are not body clearance.
    if (selectedDiagnostics.some(diagnostic => !retainedRouteWarning(diagnostic)) || scene.diagnostics.some(diagnostic => worsened(diagnostic))) {
      continue;
    }
    const remaining = new Map(selectedDiagnostics.map(diagnostic => [signature(diagnostic), severity(scene, diagnostic)]));
    if (!selectedConflicts.some(diagnostic => !remaining.has(signature(diagnostic)) ||
        remaining.get(signature(diagnostic))! < existing.get(signature(diagnostic))! - 1e-6)) continue;
    // Other anchors, including pins, stay put. Containing frames may resize.
    if (original.nodes.some(node => !moving.has(node.id) && !ancestors.has(node.id) &&
        (() => { const after = scene.nodes.find(item => item.id === node.id); return !after || after.x !== node.x || after.y !== node.y || after.width !== node.width || after.height !== node.height; })())) continue;
    return { status: 'ready', id, operation: { type: 'move', ids: [id], dx, dy, ...(scope === undefined ? {} : { scope: moveScope }) }, scene, candidateCount };
  }
  return { status: 'unavailable', reason: '暂未找到保持其他对象位置且连线畅通的修复位置。可手动增大间距，或撤销这次移动。' };
}
