import { buildScene } from './core/index.ts';
import { draftHistory, parseDraftCache } from './authoring.ts';
import type { AuthoredDraft, DraftHistory } from './authoring.ts';
import type { CanvasDocument, Scene } from './core/types.ts';
import type { ImportedSourceDraft } from './api.ts';
import { cameraViewportSize, resizeCameraViewport } from './cameraViewport.ts';
import type { CameraViewport } from './cameraViewport.ts';

export type DraftCamera = { x: number; y: number; zoom: number };
export type AuthoringWorkspace = { draft: AuthoredDraft; history?: DraftHistory; storageRevision?: number; savedRevision?: number;
  selection?: string[]; camera?: DraftCamera; viewport?: CameraViewport; tool?: 'select' | 'pan'; sourceHistory?: { past: number; future: number }; viewBaseline?: AuthoredDraft };
export type SourceAuthoringView = { selection: string[]; camera: DraftCamera; viewport?: CameraViewport; tool: 'select' | 'pan'; sourceHistory: { past: number; future: number } };
export type RebaseSourceDraft = (draft: AuthoredDraft, document: CanvasDocument, scene: Scene) => Promise<ImportedSourceDraft>;

export function sourceAuthoringKey(document: CanvasDocument): string {
  return JSON.stringify([document.id, document.sourceBindingDigest, document.architecture.irDigest]);
}
function assertSourceBinding(draft: AuthoredDraft, document: CanvasDocument) {
  const source = draft.sourceProvenance;
  if (!source || source.documentId !== document.id || source.sourceDigest !== document.sourceBindingDigest ||
      source.sourceDigest !== document.architecture.sourceDigest || source.irDigest !== document.architecture.irDigest) {
    throw new Error('源码或 IR 摘要已改变；保留原搭建会话，不能将其编辑或撤销记录绑定到新模型。');
  }
}
function selectedDraftIds(draft: AuthoredDraft, canonicalIds: readonly string[]) {
  const visible = new Set(draft.nodes.map(node => node.id)), refs = draft.sourceProvenance?.nodeRefs ?? {};
  return canonicalIds.flatMap(id => Object.entries(refs).filter(([draftId, ref]) => visible.has(draftId) && (ref.sceneNodeId === id || ref.nodeId === id)).map(([draftId]) => draftId));
}
export function followSourceView(workspace: AuthoringWorkspace, view: SourceAuthoringView): AuthoringWorkspace {
  return { ...workspace, selection: [...new Set(selectedDraftIds(workspace.draft, view.selection))],
    camera: { ...view.camera }, viewport: view.viewport ? { ...view.viewport } : undefined, tool: view.tool, sourceHistory: { ...view.sourceHistory } };
}
export function authoringCameraAtViewport(camera: DraftCamera, previous: CameraViewport | undefined, next: CameraViewport): DraftCamera {
  return previous ? resizeCameraViewport(camera, previous, next) ?? camera : camera;
}

/** Keep historical hierarchy differences while applying the latest source canvas baseline. */
function historyFrontier(document: CanvasDocument, snapshot: AuthoredDraft, current: AuthoredDraft): CanvasDocument {
  const next = structuredClone(document), currentExpanded = new Set(current.sourceProvenance!.canvas.expandedIds),
    snapshotExpanded = new Set(snapshot.sourceProvenance!.canvas.expandedIds), expanded = new Set(next.expandedIds);
  for (const node of next.architecture.nodes) {
    if (snapshotExpanded.has(node.id) !== currentExpanded.has(node.id)) {
      if (snapshotExpanded.has(node.id)) expanded.add(node.id); else expanded.delete(node.id);
    }
  }
  next.expandedIds = [...expanded];
  return next;
}

/** Carry local presentation deltas; untouched source presentation follows the new canvas. */
function preservePresentationEdits(before: AuthoredDraft, rebased: AuthoredDraft): AuthoredDraft {
  const result = structuredClone(rebased), previous = new Map(before.nodes.map(node => [node.id, node])),
    oldBaseline = new Map(before.sourceProvenance!.originalGraph.nodes.map(node => [node.id, node])),
    newBaseline = new Map(result.sourceProvenance!.originalGraph.nodes.map(node => [node.id, node]));
  for (const node of result.nodes) {
    const edited = previous.get(node.id), old = oldBaseline.get(node.id), fresh = newBaseline.get(node.id);
    if (!edited || !old || !fresh) continue;
    node.position = { x: fresh.position.x + edited.position.x - old.position.x,
      y: fresh.position.y + edited.position.y - old.position.y };
    if (edited.label === old.label) node.label = fresh.label;
    if (node.presentation && fresh.presentation && old.presentation && edited.presentation) {
      for (const key of ['fill', 'stroke'] as const) {
        node.presentation[key] = edited.presentation[key] === old.presentation[key] ? fresh.presentation[key] : edited.presentation[key];
      }
    }
  }
  // The cache is persisted and later expansion reads it. Update any live copy
  // to the same rebased anchor instead of resurrecting a stale position.
  if (result.sourceCache) {
    const live = new Map(result.nodes.map(node => [node.id, node]));
    result.sourceCache.nodes = result.sourceCache.nodes.map(node => structuredClone(live.get(node.id) ?? node));
  }
  result.revision = before.revision;
  return result;
}

/** All snapshots are rebased before returning; a failed snapshot leaves the old session intact. */
export async function resumeSourceAuthoring(workspace: AuthoringWorkspace, document: CanvasDocument,
  view: SourceAuthoringView, rebase: RebaseSourceDraft): Promise<AuthoringWorkspace> {
  const history = workspace.history ?? draftHistory(workspace.draft);
  for (const snapshot of [history.draft, ...history.past, ...history.future]) assertSourceBinding(snapshot, document);
  if (history.draft.sourceProvenance!.visualRevision === document.revision) return followSourceView(workspace, view);
  const project = async (snapshot: AuthoredDraft, current = false) => {
    const frontier = current ? document : historyFrontier(document, snapshot, history.draft);
    const response = await rebase(structuredClone(snapshot), frontier, buildScene(frontier));
    assertSourceBinding(response.draft, document);
    if (response.draft.id !== snapshot.id) throw new Error('重投影改变了搭建会话身份；原会话已保留。');
    return preservePresentationEdits(snapshot, response.draft);
  };
  // Keep a bounded number of server requests in flight and publish atomically.
  const draft = await project(history.draft, true), past: AuthoredDraft[] = [], future: AuthoredDraft[] = [];
  for (const snapshot of history.past) past.push(await project(snapshot));
  for (const snapshot of history.future) future.push(await project(snapshot));
  const changed = JSON.stringify(draft) !== JSON.stringify(history.draft);
  if (changed) draft.revision = history.draft.revision + 1;
  const viewBaseline = workspace.viewBaseline ? await project(workspace.viewBaseline, true) : undefined;
  return followSourceView({ ...workspace, draft, history: { draft, past, future }, viewBaseline }, view);
}

/** Reopening server bytes retains existing undo and the current view. */
export function reopenAuthoringWorkspace(workspace: AuthoringWorkspace, saved: AuthoredDraft, storageRevision: number): AuthoringWorkspace {
  if (saved.id !== workspace.draft.id) throw new Error('保存记录属于其他模型草稿；当前编辑已保留。');
  if (workspace.draft.sourceProvenance) assertSourceBinding(saved, workspace.draft.sourceProvenance.canvas);
  const history = workspace.history ?? draftHistory(workspace.draft);
  const equivalent = (draft: AuthoredDraft) => JSON.stringify({ ...draft, revision: 0 });
  const next = equivalent(saved) === equivalent(history.draft) ? history : {
    draft: { ...structuredClone(saved), revision: history.draft.revision + 1 },
    past: [...history.past.slice(-79), history.draft], future: [] };
  const visible = new Set(next.draft.nodes.map(node => node.id));
  return { ...workspace, draft: next.draft, history: next, storageRevision, savedRevision: next.draft.revision,
    selection: workspace.selection?.filter(id => visible.has(id)) ?? [] };
}

/** Browser recovery keeps two real histories separate; it never manufactures source undo. */
export function parseAuthoringWorkspace(value: unknown): AuthoringWorkspace | null {
  const base = parseDraftCache(value);
  if (!base || !value || typeof value !== 'object') return null;
  const raw = value as Record<string, unknown>, history = raw.history as DraftHistory | undefined;
  let recovered = draftHistory(base.draft);
  if (history) {
    if (!Array.isArray(history.past) || !Array.isArray(history.future) || history.past.length > 80 || history.future.length > 80 ||
        JSON.stringify(history.draft) !== JSON.stringify(base.draft)) return null;
    for (const snapshot of [...history.past, ...history.future]) {
      if (!parseDraftCache({ draft: snapshot, storageRevision: 0, savedRevision: -1 }) || snapshot.id !== base.draft.id) return null;
      if (base.draft.sourceProvenance) {
        try { assertSourceBinding(snapshot, base.draft.sourceProvenance.canvas); } catch { return null; }
      } else if (snapshot.sourceProvenance) return null;
    }
    recovered = structuredClone(history);
  }
  const camera = raw.camera as DraftCamera | undefined;
  if (camera && (!Number.isFinite(camera.x) || !Number.isFinite(camera.y) || !Number.isFinite(camera.zoom) || camera.zoom < .04 || camera.zoom > 6)) return null;
  const visible = new Set(base.draft.nodes.map(node => node.id));
  if (raw.selection && (!Array.isArray(raw.selection) || !raw.selection.every(id => typeof id === 'string'))) return null;
  if (raw.tool && raw.tool !== 'select' && raw.tool !== 'pan') return null;
  const viewBaseline = raw.viewBaseline === undefined ? undefined : parseDraftCache({ draft: raw.viewBaseline, storageRevision: 0, savedRevision: -1 })?.draft;
  if (raw.viewBaseline !== undefined && (!viewBaseline || viewBaseline.id !== base.draft.id)) return null;
  return { ...base, history: recovered, selection: (raw.selection as string[] | undefined)?.filter(id => visible.has(id)) ?? [],
    camera: camera ? { ...camera } : undefined, viewport: cameraViewportSize(raw.viewport as CameraViewport | undefined) ?? undefined, tool: raw.tool as AuthoringWorkspace['tool'], viewBaseline };
}
