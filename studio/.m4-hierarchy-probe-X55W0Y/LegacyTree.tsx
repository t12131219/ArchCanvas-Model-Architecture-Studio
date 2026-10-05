import type { Architecture, ArchitectureNode, CanvasDocument } from './core';
import { Icon } from './icons';

function TreeNode({ node, architecture, document, selected, onSelect, onExpand, depth = 0 }: { node: ArchitectureNode; architecture: Architecture; document: CanvasDocument; selected: string[]; onSelect: (id: string) => void; onExpand: (id: string, expanded: boolean) => void; depth?: number }) {
  const expanded = document.expandedIds.includes(node.id);
  return <div role="treeitem" data-tree-node-id={node.id} data-tree-depth={depth} aria-expanded={node.children.length ? expanded : undefined} aria-selected={selected.includes(node.id)}><div className={`tree-row ${selected.includes(node.id) ? 'selected' : ''}`} style={{ paddingLeft: 14 + depth * 13 }}><button className={`tree-toggle ${expanded ? 'open' : ''}`} disabled={!node.children.length} aria-label={`${expanded ? '收起' : '展开'} ${node.label}`} onClick={() => onExpand(node.id, !expanded)}><Icon name="chevron" size={11} /></button><button className="tree-label" onClick={() => onSelect(node.id)}><span className={`tree-node-dot ${node.category}`} /><span>{document.displayAliases[node.id] ?? node.label}</span>{node.repeat && <small>×{node.repeat.count}</small>}</button>{document.pinnedObjects.includes(node.id) && <Icon name="pin" size={10} />}</div>{expanded && node.children.map(id => { const child = architecture.nodes.find(n => n.id === id); return child ? <TreeNode key={id} node={child} architecture={architecture} document={document} selected={selected} onSelect={onSelect} onExpand={onExpand} depth={depth + 1} /> : null; })}</div>;
}

export { TreeNode };
