import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { memo, useMemo } from 'react';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-oMdYP7/icons.mjs';
export const HierarchyTree = memo(function HierarchyTree({ architecture, document, selected, onSelect, onExpand }) {
    const { roots, byId } = useMemo(() => {
        const roots = [];
        const byId = new Map();
        for (const node of architecture.nodes) {
            byId.set(node.id, node);
            if (!node.parentId)
                roots.push(node);
        }
        return { roots, byId };
    }, [architecture]);
    const expanded = useMemo(() => new Set(document.expandedIds), [document.expandedIds]);
    const selectedIds = useMemo(() => new Set(selected), [selected]);
    const pinned = useMemo(() => new Set(document.pinnedObjects), [document.pinnedObjects]);
    const state = { byId, aliases: document.displayAliases, expanded, selected: selectedIds, pinned, onSelect, onExpand };
    return _jsx(_Fragment, { children: roots.map(node => _jsx(TreeNode, { node: node, state: state }, node.id)) });
});
function TreeNode({ node, state, depth = 0 }) {
    const expanded = state.expanded.has(node.id);
    const selected = state.selected.has(node.id);
    return _jsxs("div", { role: "treeitem", "data-tree-node-id": node.id, "data-tree-depth": depth, "aria-expanded": node.children.length ? expanded : undefined, "aria-selected": selected, children: [_jsxs("div", { className: `tree-row ${selected ? 'selected' : ''}`, style: { paddingLeft: 14 + depth * 13 }, children: [_jsx("button", { className: `tree-toggle ${expanded ? 'open' : ''}`, disabled: !node.children.length, "aria-label": `${expanded ? '收起' : '展开'} ${node.label}`, onClick: () => state.onExpand(node.id, !expanded), children: _jsx(Icon, { name: "chevron", size: 11 }) }), _jsxs("button", { className: "tree-label", onClick: () => state.onSelect(node.id), children: [_jsx("span", { className: `tree-node-dot ${node.category}` }), _jsx("span", { children: state.aliases[node.id] ?? node.label }), node.repeat && _jsxs("small", { children: ["\u00D7", node.repeat.count] })] }), state.pinned.has(node.id) && _jsx(Icon, { name: "pin", size: 10 })] }), expanded && node.children.map(id => {
                const child = state.byId.get(id);
                return child ? _jsx(TreeNode, { node: child, state: state, depth: depth + 1 }, id) : null;
            })] });
}
