import type { CanvasDocument, MoveScope, Scene, SceneDiagnostic, VisualOperation } from './types.ts';
import { resolveMoveScope } from './document.ts';
import { buildScene } from './scene.ts';
import { prepareMovePreview, previewMoveScene } from './movePreview.ts';
import { TOKENS } from './tokens.ts';
import { validateDocument } from './validate.ts';
import { orthogonalPathPoints } from './orthogonalRouter.ts';

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
  return JSON.stringify([diagnostic.code, diagnostic.objectIds, diagnostic.edgeId]);
}
function conflicts(scene: Scene, moving: Set<string>): SceneDiagnostic[] {
  const incidentEdges = new Set(scene.edges.filter(edge => moving.has(edge.sourceId) || moving.has(edge.targetId)).map(edge => edge.id));
  return scene.diagnostics.filter(diagnostic => diagnostic.code &&
    (diagnostic.objectIds?.some(id => moving.has(id)) || (diagnostic.edgeId && incidentEdges.has(diagnostic.edgeId))));
}
function severity(scene: Scene, diagnostic: SceneDiagnostic): number {
  const byId = new Map(scene.nodes.map(node => [node.id, node]));
  const [first, second] = (diagnostic.objectIds ?? []).map(id => byId.get(id));
  const area = (a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) =>
    Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) *
    Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  if (first && second && diagnostic.code === 'layout-overlap') return area(first, second);
  if (first && second && diagnostic.code === 'layout-header-overlap') return area(first, { ...second, height: second.headerHeight + 4 });
  if (first && second && diagnostic.code === 'layout-outside-parent') return Math.max(0, second.x - first.x) + Math.max(0, second.y - first.y) +
    Math.max(0, first.x + first.width - second.x - second.width) + Math.max(0, first.y + first.height - second.y - second.height);
  if (diagnostic.code !== 'layout-route-blocked') return 0;
  const edge = scene.edges.find(item => item.id === diagnostic.edgeId);
  if (!edge) return 0;
  const ancestor = (id: string, child: string) => {
    let parent = byId.get(child)?.parentId;
    while (parent) { if (parent === id) return true; parent = byId.get(parent)?.parentId; }
    return false;
  };
  const points = orthogonalPathPoints(edge.path);
  let length = 0;
  for (const id of diagnostic.objectIds ?? []) {
    const body = byId.get(id); if (!body) continue;
    const height = ancestor(id, edge.sourceId) || ancestor(id, edge.targetId) ? body.headerHeight + 4 : body.height;
    for (let index = 1; index < points.length; index++) {
      const a = points[index - 1], b = points[index];
      if (a.y === b.y && a.y > body.y + 1e-6 && a.y < body.y + height - 1e-6) length += Math.max(0, Math.min(Math.max(a.x, b.x), body.x + body.width) - Math.max(Math.min(a.x, b.x), body.x));
      if (a.x === b.x && a.x > body.x + 1e-6 && a.x < body.x + body.width - 1e-6) length += Math.max(0, Math.min(Math.max(a.y, b.y), body.y + height) - Math.max(Math.min(a.y, b.y), body.y));
    }
  }
  return length;
}

/** An explicit proposal, never an implicit clamp or a change to source facts. */
export function planLayoutRecovery(document: CanvasDocument, id: string, scope?: MoveScope): LayoutRecoveryPlan {
  validateDocument(document);
  const moveScope = resolveMoveScope(scope);
  const original = buildScene(document), selected = original.nodes.find(node => node.id === id);
  if (!selected) return { status: 'unavailable', reason: '请先选择一个当前可见的对象。' };
  const moving = descendants(document, id);
  if (document.pinnedObjects.some(pin => moving.has(pin))) return { status: 'unavailable', reason: '选中对象或其内部对象已固定。取消固定后再预览位置修复。' };
  const selectedConflicts = conflicts(original, moving);
  if (!selectedConflicts.length) return { status: 'unneeded', reason: '这个对象没有需要修复的布局冲突。' };
  if (selectedConflicts.some(diagnostic => diagnostic.code !== 'layout-route-blocked' && (diagnostic.objectIds?.length ?? 0) >= 2 && diagnostic.objectIds!.every(item => moving.has(item)))) {
    return { status: 'unavailable', reason: '冲突发生在选中容器内部。请先选择越界或重叠的内部对象，再预览位置修复。' };
  }

  const byId = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const ancestors = new Set<string>();
  let parentId = byId.get(id)?.parentId;
  while (parentId) { ancestors.add(parentId); parentId = byId.get(parentId)?.parentId; }
  const parent = original.nodes.find(node => node.id === selected.parentId);
  const left = parent?.expanded ? parent.x + TOKENS.padding : Number.NEGATIVE_INFINITY;
  const top = parent?.expanded ? parent.y + parent.headerHeight + 16 : Number.NEGATIVE_INFINITY;
  const obstacles = original.nodes.filter(node => !moving.has(node.id) && !ancestors.has(node.id));
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
  const session = prepareMovePreview(document, [id], moveScope);
  let candidateCount = 0;
  for (const position of candidates) {
    candidateCount++;
    const dx = position.x - selected.x, dy = position.y - selected.y;
    const scene = previewMoveScene(session, dx, dy);
    if (conflicts(scene, moving).length || scene.diagnostics.some(diagnostic => diagnostic.code &&
        (!existing.has(signature(diagnostic)) || severity(scene, diagnostic) > existing.get(signature(diagnostic))! + 1e-6))) continue;
    // Other anchors, including pins, stay put. Containing frames may resize.
    if (original.nodes.some(node => !moving.has(node.id) && !ancestors.has(node.id) &&
        (() => { const after = scene.nodes.find(item => item.id === node.id); return !after || after.x !== node.x || after.y !== node.y || after.width !== node.width || after.height !== node.height; })())) continue;
    return { status: 'ready', id, operation: { type: 'move', ids: [id], dx, dy, ...(scope === undefined ? {} : { scope: moveScope }) }, scene, candidateCount };
  }
  return { status: 'unavailable', reason: '暂未找到保持其他对象位置且连线畅通的修复位置。可手动增大间距，或撤销这次移动。' };
}
