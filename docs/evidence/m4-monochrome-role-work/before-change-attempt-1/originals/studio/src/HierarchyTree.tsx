import { memo, useMemo } from 'react';
import type { Architecture, ArchitectureNode, CanvasDocument } from './core';
import { Icon } from './icons';

type HierarchyTreeProps = {
  architecture: Architecture;
  document: CanvasDocument;
  selected: readonly string[];
  onSelect: (id: string) => void;
  onExpand: (id: string, expanded: boolean) => void;
};

type TreeState = {
  byId: ReadonlyMap<string, ArchitectureNode>;
  aliases: CanvasDocument['displayAliases'];
  expanded: ReadonlySet<string>;
  selected: ReadonlySet<string>;
  pinned: ReadonlySet<string>;
  onSelect: HierarchyTreeProps['onSelect'];
  onExpand: HierarchyTreeProps['onExpand'];
};

export const HierarchyTree = memo(function HierarchyTree({ architecture, document, selected, onSelect, onExpand }: HierarchyTreeProps) {
  const { roots, byId } = useMemo(() => {
    const roots: ArchitectureNode[] = [];
    const byId = new Map<string, ArchitectureNode>();
    for (const node of architecture.nodes) {
      byId.set(node.id, node);
      if (!node.parentId) roots.push(node);
    }
    return { roots, byId };
  }, [architecture]);
  const expanded = useMemo(() => new Set(document.expandedIds), [document.expandedIds]);
  const selectedIds = useMemo(() => new Set(selected), [selected]);
  const pinned = useMemo(() => new Set(document.pinnedObjects), [document.pinnedObjects]);
  const state: TreeState = { byId, aliases: document.displayAliases, expanded, selected: selectedIds, pinned, onSelect, onExpand };

  return <>{roots.map(node => <TreeNode key={node.id} node={node} state={state} />)}</>;
});

function TreeNode({ node, state, depth = 0 }: { node: ArchitectureNode; state: TreeState; depth?: number }) {
  const expanded = state.expanded.has(node.id);
  const selected = state.selected.has(node.id);

  return <div role="treeitem" data-tree-node-id={node.id} data-tree-depth={depth} aria-expanded={node.children.length ? expanded : undefined} aria-selected={selected}>
    <div className={`tree-row ${selected ? 'selected' : ''}`} style={{ paddingLeft: 14 + depth * 13 }}>
      <button className={`tree-toggle ${expanded ? 'open' : ''}`} disabled={!node.children.length} aria-label={`${expanded ? '收起' : '展开'} ${node.label}`} onClick={() => state.onExpand(node.id, !expanded)}><Icon name="chevron" size={11} /></button>
      <button className="tree-label" onClick={() => state.onSelect(node.id)}><span className={`tree-node-dot ${node.category}`} /><span>{state.aliases[node.id] ?? node.label}</span>{node.repeat && <small>×{node.repeat.count}</small>}</button>
      {state.pinned.has(node.id) && <Icon name="pin" size={10} />}
    </div>
    {expanded && node.children.map(id => {
      const child = state.byId.get(id);
      return child ? <TreeNode key={id} node={child} state={state} depth={depth + 1} /> : null;
    })}
  </div>;
}
