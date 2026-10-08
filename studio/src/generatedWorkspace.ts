import { changeDraft, draftHistory } from './authoring.ts';
import type { AuthoredDraft } from './authoring.ts';
import { buildScene } from './core/index.ts';
import type { CanvasDocument } from './core/types.ts';
import { parseAuthoringWorkspace, sourceAuthoringKey } from './sourceAuthoringSession.ts';
import type { AuthoringWorkspace, SourceAuthoringView } from './sourceAuthoringSession.ts';

export type GeneratedWorkspaceBinding = { workspaceKey: string; documentId: string; sourceDigest: string; irDigest: string;
  draft: AuthoredDraft; nodeBindings: Record<string, string>; visualRevision: number };

export function sameGeneratedDraft(a: AuthoredDraft, b: AuthoredDraft) {
  // HTTP normalization can reorder object keys; array order and every value
  // remain significant. Revision alone is outside generation identity.
  const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical) :
    value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined)
      .sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value;
  return JSON.stringify(canonical({ ...a, revision: 0 })) === JSON.stringify(canonical({ ...b, revision: 0 }));
}

/** Translate the generated view by certified node bindings before rebasing the
 * original source draft. Source/IR identity stays that of the original corpus. */
export function generatedSourceView(workspace: AuthoringWorkspace, document: CanvasDocument, binding: GeneratedWorkspaceBinding): CanvasDocument | null {
  const source = workspace.draft.sourceProvenance;
  if (!source || document.revision === binding.visualRevision) return null;
  if (binding.documentId !== document.id || binding.sourceDigest !== document.sourceBindingDigest || binding.irDigest !== document.architecture.irDigest)
    throw new Error('生成视图的源码绑定已变化，不能重投影原编辑草稿。');
  const translated = structuredClone(source.canvas), expanded = new Set(translated.expandedIds);
  const generated = new Map(buildScene(document).nodes.map(node => [node.id, node]));
  const refs = new Map(Object.entries(source.nodeRefs).flatMap(([id, ref]) => binding.nodeBindings[id] ? [[ref.nodeId, binding.nodeBindings[id]] as const] : []));
  for (const fact of translated.architecture.nodes) {
    const target = refs.get(fact.id);
    if (!target) continue;
    if (document.expandedIds.includes(target)) expanded.add(fact.id); else expanded.delete(fact.id);
    const node = generated.get(target);
    if (!node) continue;
    const parentTarget = fact.parentId ? refs.get(fact.parentId) : undefined;
    const parent = parentTarget ? generated.get(parentTarget) : undefined;
    translated.layout[fact.id] = { x: node.x - (parent?.x ?? 0), y: node.y - (parent?.y ?? 0), width: node.width, height: node.height };
    translated.nodeStyleOverrides[fact.id] = { ...document.nodeStyleOverrides[target] };
    translated.displayAliases[fact.id] = node.label;
  }
  translated.expandedIds = [...expanded]; translated.layoutByFrontier = {};
  translated.revision = Math.max(source.visualRevision, translated.revision) + document.revision + 1;
  return translated;
}
/** Return to the actual authoring history, carrying subsequent visual edits back. */
export function resumeGeneratedWorkspace(workspace: AuthoringWorkspace, document: CanvasDocument,
  binding: GeneratedWorkspaceBinding, view: SourceAuthoringView): AuthoringWorkspace {
  if (binding.documentId !== document.id || binding.sourceDigest !== document.sourceBindingDigest || binding.irDigest !== document.architecture.irDigest)
    throw new Error('浏览视图的源码绑定已变化，不能恢复为原编辑草稿。');
  const scene = buildScene(document), nodes = new Map(scene.nodes.map(node => [node.id, node]));
  let history = workspace.history ?? draftHistory(workspace.draft);
  if (document.revision !== binding.visualRevision) history = changeDraft(history, draft => {
    for (const node of draft.nodes) {
      const canonical = binding.nodeBindings[node.id], visible = nodes.get(canonical);
      if (!visible) continue;
      node.position = { x: visible.x, y: visible.y }; node.label = visible.label;
      node.visual = { width: visible.width, height: visible.height, fill: visible.fill, stroke: visible.stroke };
      if (node.presentation) {
        const before = node.presentation;
        node.presentation = { ...before, width: visible.width, height: visible.height, fill: visible.fill, stroke: visible.stroke,
          ports: Object.fromEntries(Object.entries(before.ports).map(([id, p]) => [id, { x: p.x * visible.width / before.width, y: p.y * visible.height / before.height }])) };
      }
    }
    if (draft.sourceCache) {
      const visible = new Map(draft.nodes.map(node => [node.id, node]));
      draft.sourceCache.nodes = draft.sourceCache.nodes.map(node => structuredClone(visible.get(node.id) ?? node));
    }
  });
  const selected = new Set(view.selection);
  return { ...workspace, draft: history.draft, history, viewBaseline: structuredClone(history.draft),
    selection: history.draft.nodes.filter(node => selected.has(binding.nodeBindings[node.id])).map(node => node.id),
    camera: { ...view.camera }, viewport: view.viewport, tool: view.tool, sourceHistory: view.sourceHistory };
}

export type GeneratedWorkspaceStorage = Pick<Storage, 'getItem' | 'setItem'>;
const CACHE_PREFIX = 'archcanvas.generated-workspace.v1:';

/** Recover only a draft bound to this exact saved model generation. */
export function readGeneratedWorkspace(storage: GeneratedWorkspaceStorage, document: CanvasDocument): { binding: GeneratedWorkspaceBinding; workspace: AuthoringWorkspace } | null {
  try {
    const raw = JSON.parse(storage.getItem(CACHE_PREFIX + sourceAuthoringKey(document)) ?? 'null');
    if (!raw || raw.schemaVersion !== 1 || !raw.binding) return null;
    const b = raw.binding as GeneratedWorkspaceBinding, workspace = parseAuthoringWorkspace(raw.workspace);
    const baseline = parseAuthoringWorkspace({ draft: b.draft, storageRevision: 0, savedRevision: -1 });
    if (!workspace || !baseline || workspace.draft.id !== baseline.draft.id || typeof b.workspaceKey !== 'string' || !b.workspaceKey ||
      b.documentId !== document.id || b.sourceDigest !== document.sourceBindingDigest || b.irDigest !== document.architecture.irDigest ||
      !Number.isSafeInteger(b.visualRevision) || b.visualRevision < 0 || !b.nodeBindings || typeof b.nodeBindings !== 'object' || Array.isArray(b.nodeBindings)) return null;
    const draftIds = new Set([...b.draft.nodes, ...(b.draft.sourceCache?.nodes ?? [])].map(node => node.id));
    const canonical = new Set(document.architecture.nodes.map(node => node.id));
    const bindings = Object.entries(b.nodeBindings);
    if (bindings.some(([id, target]) => !draftIds.has(id) || typeof target !== 'string' || !canonical.has(target)) || new Set(bindings.map(([, target]) => target)).size !== bindings.length) return null;
    return { binding: structuredClone(b), workspace };
  } catch { return null; }
}

export function writeGeneratedWorkspace(storage: GeneratedWorkspaceStorage, workspace: AuthoringWorkspace, binding: GeneratedWorkspaceBinding) {
  const key = JSON.stringify([binding.documentId, binding.sourceDigest, binding.irDigest]);
  storage.setItem(CACHE_PREFIX + key, JSON.stringify({ schemaVersion: 1, workspace, binding }));
}

export function authoringViewSelection(workspace: AuthoringWorkspace, binding?: GeneratedWorkspaceBinding): string[] {
  return (workspace.selection ?? []).flatMap(id => {
    const canonical = binding?.nodeBindings[id] ?? workspace.draft.sourceProvenance?.nodeRefs[id]?.sceneNodeId;
    return canonical ? [canonical] : [];
  });
}
