import type { AuthoredDraft } from './authoring.ts';

export type SourceStructureEntry = { id: string; label: string; kind: string; parentId?: string; children: string[];
  draftId?: string; deleted: boolean; source?: string; definitionId?: string };

/** Inventory uses the frozen hierarchy, including never-opened descendants. */
export function sourceStructureEntries(draft: AuthoredDraft): SourceStructureEntry[] {
  const source = draft.sourceProvenance;
  if (!source) return [];
  const visible = new Set(draft.nodes.map(node => node.id));
  const refs = new Map(Object.entries(source.nodeRefs).map(([id, ref]) => [ref.nodeId, id]));
  const missing = new Set([...(draft.sourceCache?.removedNodeIds ?? []),
    ...source.originalGraph.nodes.filter(node => !visible.has(node.id)).map(node => node.id)]);
  const removed = new Set([...missing].flatMap(id => source.nodeRefs[id] ? [source.nodeRefs[id].nodeId] : []));
  const facts = new Map(source.architecture.nodes.map(node => [node.id, node]));
  return source.architecture.nodes.map(node => {
    let id: string | undefined = node.id, deleted = false;
    while (id) { if (removed.has(id)) { deleted = true; break; } id = facts.get(id)?.parentId; }
    const draftId = refs.get(node.id);
    return { id: node.id, label: source.canvas.displayAliases[node.id] ?? node.label, kind: node.kind,
      parentId: node.parentId, children: node.children, deleted, draftId: draftId && visible.has(draftId) ? draftId : undefined,
      definitionId: !node.children.length && typeof node.parameters.definitionReference === 'string' && facts.get(node.parameters.definitionReference)?.children.length ? node.parameters.definitionReference : undefined,
      source: node.source && `${node.source.path}:${node.source.line}` };
  });
}

export function filterSourceStructure(entries: SourceStructureEntry[], query: string): Set<string> {
  const text = query.trim().toLowerCase(), byId = new Map(entries.map(entry => [entry.id, entry]));
  const matches = new Set<string>();
  for (const entry of entries) if (!text || `${entry.label} ${entry.kind} ${entry.source ?? ''}`.toLowerCase().includes(text)) {
    let id: string | undefined = entry.id;
    while (id && !matches.has(id)) { matches.add(id); id = byId.get(id)?.parentId; }
  }
  return matches;
}
