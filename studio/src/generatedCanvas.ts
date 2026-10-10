import { buildScene } from './core/scene.ts';
import { createDocument } from './core/document.ts';
import { validateDocument } from './core/validate.ts';
import type { Architecture, EdgeStyle } from './core/types.ts';
import { TOKENS } from './core/tokens.ts';
import { textWidth } from './core/typography.ts';
import type { AuthoredDraft, DraftNode } from './authoring.ts';
import { sameGeneratedDraft } from './generatedWorkspace.ts';
import { portLayoutKey } from './core/portRouting.ts';

type GeneratedBindings = {
  nodeBindings: Record<string, string>;
  containerBindings?: Record<string, string>;
  edgeBindings?: Record<string, string[]>;
};

/** Use the retained view hierarchy while carrying actual editor changes.
 * Source groups have independent expanded and collapsed dimensions. */
function sourceViewNodes(draft: AuthoredDraft): DraftNode[] {
  const source = draft.sourceProvenance;
  if (!source?.viewGraph) return draft.nodes;
  const current = new Map(draft.nodes.map(node => [node.id, node]));
  const baseline = new Map(source.originalGraph.nodes.map(node => [node.id, node]));
  const viewIds = new Set(source.viewGraph.nodes.map(node => node.id));
  const visible = source.viewGraph.nodes.flatMap(viewNode => {
    const edited = current.get(viewNode.id), original = baseline.get(viewNode.id);
    if (!edited) return [];
    const node = structuredClone(edited);
    node.position = { x: viewNode.position.x + edited.position.x - (original?.position.x ?? edited.position.x),
      y: viewNode.position.y + edited.position.y - (original?.position.y ?? edited.position.y) };
    node.presentation = structuredClone(viewNode.presentation);
    if (node.presentation && edited.presentation) {
      node.presentation.fill = edited.visual?.fill ?? edited.presentation.fill;
      node.presentation.stroke = edited.visual?.stroke ?? edited.presentation.stroke;
    }
    if (edited.presentation?.group !== viewNode.presentation?.group) delete node.visual;
    return [node];
  });
  // New registered operators stay visible. Their tensor edges are projected
  // from the certified generated architecture, including hidden source ends.
  return [...visible, ...draft.nodes.filter(node => !viewIds.has(node.id) && !source.nodeRefs[node.id])];
}

/** Apply visual state only through the generator's independently checked IDs. */
export function createGeneratedCanvas(architecture: Architecture, generationDraft: AuthoredDraft, bindings: GeneratedBindings, presentationDraft = generationDraft) {
  const byId = new Map(architecture.nodes.map(node => [node.id, node]));
  const bound = new Map<string, DraftNode>();
  const draft = presentationDraft, presentationNodes = sourceViewNodes(draft), draftIds = new Set(presentationNodes.map(node => node.id));
  const generationMapping = { ...bindings.nodeBindings, ...bindings.containerBindings }, used = new Set<string>();
  for (const [draftId, id] of Object.entries(generationMapping)) {
    const node = generationDraft.nodes.find(item => item.id === draftId);
    if (!node || !byId.has(id) || used.has(id)) throw new Error('生成模型的部件映射不唯一，已保留原草稿。');
    used.add(id);
  }
  const sourceMatches = draft.sourceProvenance && generationDraft.sourceProvenance &&
    draft.sourceProvenance.sourceDigest === generationDraft.sourceProvenance.sourceDigest &&
    draft.sourceProvenance.irDigest === generationDraft.sourceProvenance.irDigest;
  const authoredMatches = !draft.sourceProvenance && !generationDraft.sourceProvenance && sameGeneratedDraft(draft, generationDraft);
  if (presentationDraft !== generationDraft && (draft.id !== generationDraft.id || (!sourceMatches && !authoredMatches))) {
    throw new Error('生成模型的展示草稿与源码来源不一致，已保留原草稿。');
  }
  // Generation expands source regions to verify their complete graph. The
  // edited frontier stays a separate presentation snapshot; hidden bindings
  // must not cause descendants to appear when the new model is opened.
  const mapping: Record<string, string> = {};
  for (const node of presentationNodes) {
    const id = generationMapping[node.id];
    if (!id) continue;
    if (draft.sourceProvenance?.nodeRefs[node.id]?.nodeId !== generationDraft.sourceProvenance?.nodeRefs[node.id]?.nodeId) throw new Error('生成模型的部件来源映射已变化，已保留原草稿。');
    mapping[node.id] = id;
    bound.set(id, node);
  }
  const document = createDocument(architecture, draft.title, Object.fromEntries([...bound].map(([id, node]) => [id, node.label])));
  const expanded = new Set<string>();
  const collapsed = new Set([...bound].filter(([id, node]) => byId.get(id)!.children.length && node.presentation && !node.presentation.group).map(([id]) => id));
  for (const [id, node] of bound) {
    if (node.presentation?.group && byId.get(id)!.children.length) expanded.add(id);
    let parent = byId.get(id)!.parentId;
    while (parent) {
      if (collapsed.has(parent)) throw new Error('生成模型的可见部件落在已折叠区域内，已保留原草稿。');
      expanded.add(parent); parent = byId.get(parent)!.parentId;
    }
  }
  document.expandedIds = [...expanded];
  // A leaf's draft coordinate is absolute. Its source-bound layout is relative
  // to each real generated container, which must enclose the retained cards.
  const base = buildScene(document), baseById = new Map(base.nodes.map(node => [node.id, node]));
  type Box = { x: number; y: number; width: number; height: number };
  const absolute = new Map<string, Box>();
  function position(id: string): Box {
    const known = absolute.get(id); if (known) return known;
    const node = byId.get(id)!, retained = bound.get(id), fallback = baseById.get(id);
    const children = expanded.has(id) ? node.children.map(position) : [];
    const width = retained?.visual?.width ?? retained?.presentation?.width ?? fallback?.width ?? 176;
    const height = retained?.visual?.height ?? retained?.presentation?.height ?? fallback?.height ?? 100;
    let box: Box;
    if (retained) box = { ...retained.position, width, height };
    else if (children.length) {
      const header = fallback?.headerHeight ?? 39, padding = 28;
      const x = Math.min(...children.map(child => child.x)) - padding;
      const y = Math.min(...children.map(child => child.y)) - header - 16;
      const titleWidth = Math.max(TOKENS.nodeWidth, Math.min(420, textWidth(node.label) + 68)) + 20;
      box = { x, y, width: Math.max(titleWidth, Math.max(...children.map(child => child.x + child.width)) - x + padding),
        height: Math.max(header + padding, Math.max(...children.map(child => child.y + child.height)) - y + padding) };
    } else box = { x: fallback?.x ?? 0, y: fallback?.y ?? 0, width, height };
    absolute.set(id, box); return box;
  }
  architecture.nodes.filter(node => !node.parentId).forEach(node => position(node.id));
  for (const [id, box] of absolute) {
    const parentId = byId.get(id)!.parentId, parent = parentId ? absolute.get(parentId) : undefined;
    document.layout[id] = { x: box.x - (parent?.x ?? 0), y: box.y - (parent?.y ?? 0), width: box.width, height: box.height };
    const presentation = bound.get(id)?.visual ?? bound.get(id)?.presentation;
    if (presentation) document.nodeStyleOverrides[id] = { fill: presentation.fill, stroke: presentation.stroke };
  }
  document.layoutByFrontier = {};
  const original = draft.sourceProvenance?.viewCanvas ?? draft.sourceProvenance?.canvas;
  const sourceToGenerated = new Map(Object.entries(generationMapping).flatMap(([draftId, id]) => {
    const ref = draft.sourceProvenance?.nodeRefs[draftId]; return ref ? [[ref.nodeId, id] as const] : [];
  }));
  if (original) {
    document.pageSpec = structuredClone(original.pageSpec);
    document.legendItems = structuredClone(original.legendItems);
    document.annotations = structuredClone(original.annotations);
    document.pinnedObjects = original.pinnedObjects.flatMap(id => sourceToGenerated.has(id) ? [sourceToGenerated.get(id)!] : []);
    for (const [before, after] of sourceToGenerated) {
      const style = original.nodeStyleOverrides[before];
      if (style) document.nodeStyleOverrides[after] = { ...style, ...document.nodeStyleOverrides[after] };
    }
  }
  const unresolvedEdgeStyles: string[] = [], generatedEdges = new Set(architecture.edges.map(edge => edge.id));
  for (const edge of draft.edges) {
    for (const direction of ['source', 'target'] as const) {
      const endpoint = edge[direction], layout = draft.nodes.find(node => node.id === endpoint.nodeId)?.portLayouts?.[endpoint.portId];
      const ownerId = generationMapping[endpoint.nodeId];
      if (layout === undefined || !ownerId) continue;
      for (const id of bindings.edgeBindings?.[edge.id] ?? []) {
        const generated = architecture.edges.find(item => item.id === id);
        if (!generated) continue;
        const canonical = generated[direction];
        (document.portLayoutOverrides ??= {})[portLayoutKey(ownerId, canonical.nodeId, canonical.portId, generated.role)] = structuredClone(layout);
      }
    }
    const oldIds = draft.sourceProvenance?.edgeRefs[edge.id] ?? [];
    const styles = oldIds.map(id => original?.edgeStyleOverrides[id] ?? {});
    if (!styles.some(style => Object.keys(style).length)) continue;
    const sameStyle = styles.every(style => sameEdgeStyle(style, styles[0]));
    const ids = bindings.edgeBindings?.[edge.id];
    if (!sameStyle || !ids?.length || !ids.every(id => generatedEdges.has(id))) { unresolvedEdgeStyles.push(edge.id); continue; }
    for (const id of ids) document.edgeStyleOverrides[id] = structuredClone(styles[0]);
  }
  validateDocument(document);
  const unmappedNodeIds = [...draftIds].filter(id => !Object.hasOwn(mapping, id));
  return { document, unmappedNodeIds, unresolvedEdgeStyles, nodeBindings: mapping, edgeBindings: bindings.edgeBindings };
}

function sameEdgeStyle(a: EdgeStyle, b: EdgeStyle) {
  return a.stroke === b.stroke && a.width === b.width && a.dashed === b.dashed;
}
