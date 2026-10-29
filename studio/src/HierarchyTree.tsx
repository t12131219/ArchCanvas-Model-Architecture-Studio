import { t, getLocale, subscribeLocale } from './i18n';
import { memo, useMemo, useSyncExternalStore, type CSSProperties } from 'react';
import type { CanvasDocument } from './core';
import type { HierarchyNode } from './previewHierarchy';
import { Icon } from './icons';

type HierarchyTreeProps = {
  architecture: { nodes: readonly HierarchyNode[] };
  document: Pick<CanvasDocument, 'expandedIds' | 'displayAliases' | 'pinnedObjects'>;
  selected: readonly string[];
  onSelect: (id: string, additive?: boolean) => void;
  query?: string;
  mandatoryIds?: readonly string[];
  onExpand: (id: string, expanded: boolean) => void;
};

type TreeState = {
  byId: ReadonlyMap<string, HierarchyNode>;
  aliases: CanvasDocument['displayAliases'];
  expanded: ReadonlySet<string>;
  selected: ReadonlySet<string>;
  pinned: ReadonlySet<string>;
  onSelect: HierarchyTreeProps['onSelect'];
  onExpand: HierarchyTreeProps['onExpand'];
  matches: ReadonlySet<string> | null;
  mandatory: ReadonlySet<string>;
};

export const HierarchyTree = memo(function HierarchyTree({ architecture, document, selected, onSelect, onExpand, query = '', mandatoryIds = [] }: HierarchyTreeProps) {
  useSyncExternalStore(subscribeLocale, getLocale, getLocale);
  const { roots, byId } = useMemo(() => {
    const roots: HierarchyNode[] = [];
    const byId = new Map<string, HierarchyNode>();
    for (const node of architecture.nodes) {
      byId.set(node.id, node);
      if (!node.parentId) roots.push(node);
    }
    return { roots, byId };
  }, [architecture]);
  const expanded = useMemo(() => new Set(document.expandedIds), [document.expandedIds]);
  const selectedIds = useMemo(() => new Set(selected), [selected]);
  const pinned = useMemo(() => new Set(document.pinnedObjects), [document.pinnedObjects]);
  const matches = useMemo(() => {
    const text = query.trim().toLocaleLowerCase(); if (!text) return null;
    const ids = new Set<string>();
    for (const node of architecture.nodes) if (`${document.displayAliases[node.id] ?? node.label} ${node.id}`.toLocaleLowerCase().includes(text)) {
      let current: HierarchyNode | undefined = node;
      while (current && !ids.has(current.id)) { ids.add(current.id); current = current.parentId ? byId.get(current.parentId) : undefined; }
    }
    return ids;
  }, [architecture, document.displayAliases, query, byId]);
  const mandatory = useMemo(() => new Set(mandatoryIds), [mandatoryIds]);
  const state: TreeState = { byId, aliases: document.displayAliases, expanded, selected: selectedIds, pinned, onSelect, onExpand, matches, mandatory };

  return <>{matches?.size === 0 && <p className="tree-empty">{t("没有匹配的模块")}</p>}{roots.map(node => <TreeNode key={node.id} node={node} state={state} />)}</>;
});

function TreeNode({ node, state, depth = 0 }: { node: HierarchyNode; state: TreeState; depth?: number }) {
  if (state.matches && !state.matches.has(node.id)) return null;
  const expanded = !!state.matches || state.expanded.has(node.id);
  const canvasExpanded = state.expanded.has(node.id);
  const selected = state.selected.has(node.id);

  return <div role="treeitem" data-tree-node-id={node.id} data-tree-depth={depth} aria-expanded={node.children.length ? expanded : undefined} aria-selected={selected}>
    <div className={`tree-row ${selected ? 'selected' : ''}`} style={{ paddingLeft: 14 + depth * 13 }}>
      <button className={`tree-toggle ${canvasExpanded ? 'open' : ''}`} disabled={!node.children.length || state.mandatory.has(node.id)} title={state.mandatory.has(node.id) ? t("根容器保持展开") : undefined} aria-label={`${canvasExpanded ? t("收起") : t("展开")} ${node.label}`} onClick={() => state.onExpand(node.id, !canvasExpanded)}><Icon name="chevron" size={11} /></button>
      <button className="tree-label" onClick={event => state.onSelect(node.id, event.shiftKey || event.ctrlKey || event.metaKey)}><span className={`tree-node-dot ${node.category}`} /><span>{state.aliases[node.id] ?? node.label}</span>{node.repeat && <small>×{node.repeat.count}</small>}</button>
      {state.pinned.has(node.id) && <Icon name="pin" size={10} />}
    </div>
    {expanded && node.children.length > 0 && <div role="group" className="tree-children" style={{ '--tree-guide-left': `${20 + depth * 13}px` } as CSSProperties}>{node.children.map(id => {
      const child = state.byId.get(id);
      return child ? <TreeNode key={id} node={child} state={state} depth={depth + 1} /> : null;
    })}</div>}
  </div>;
}
