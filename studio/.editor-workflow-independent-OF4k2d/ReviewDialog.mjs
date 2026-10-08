import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { applyVisualBatch, buildScene, reconcileDocument, renderSvg } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/index.ts';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/icons.mjs';
import { bindingLabel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ConnectionEditor.mjs';
function figure(base, transaction, after, focus) {
    const architecture = after ? transaction.afterArchitecture : transaction.beforeArchitecture;
    if (!architecture)
        return '';
    let doc = reconcileDocument(base, architecture).document;
    for (const id of transaction.affectedNodeIds) {
        let node = architecture.nodes.find(n => n.id === id);
        while (node?.parentId) {
            const parent = architecture.nodes.find(n => n.id === node.parentId);
            if (!doc.expandedIds.includes(parent.id))
                doc = applyVisualBatch(doc, [{ type: 'expand', id: parent.id, expanded: true }]);
            node = parent;
        }
        if (architecture.nodes.some(n => n.id === id))
            doc = applyVisualBatch(doc, [{ type: 'nodeStyle', id, style: { stroke: '#bd7533' } }]);
    }
    if (transaction.intent.kind === 'RebindInput') {
        const intent = transaction.intent;
        for (const edge of architecture.edges.filter(e => e.target.nodeId === intent.nodeId && e.target.portId === intent.portId)) {
            doc = applyVisualBatch(doc, [{ type: 'edgeStyle', id: edge.id, style: { stroke: '#bd7533', width: 2.8 } }]);
        }
    }
    const scene = buildScene(doc);
    let svg = renderSvg(scene);
    if (focus) {
        const affected = new Set(transaction.affectedNodeIds);
        const context = new Set(affected);
        for (const edge of architecture.edges)
            if (affected.has(edge.source.nodeId) || affected.has(edge.target.nodeId)) {
                context.add(edge.source.nodeId);
                context.add(edge.target.nodeId);
            }
        const nodes = scene.nodes.filter(n => context.has(n.id) && !n.expanded);
        if (nodes.length) {
            const x = Math.min(...nodes.map(n => n.x)) - 20, y = Math.min(...nodes.map(n => n.y)) - 20;
            const width = Math.max(...nodes.map(n => n.x + n.width)) - x + 20;
            const height = Math.max(...nodes.map(n => n.y + n.height)) - y + 20;
            svg = svg.replace(/viewBox="[^"]*"/, `viewBox="${x} ${y} ${width} ${height}"`);
        }
    }
    return svg;
}
const statuses = { ReviewReady: '待审核', Approved: '已批准 · 待提交', Committed: '已提交', Failed: '准备失败', Stale: '版本已过期', RolledBack: '已恢复原版本', ManualRecovery: '需要手动恢复', Discarded: '已取消' };
export function ReviewDialog({ base, transaction, busy, error, onApprove, onCommit, onClose }) {
    const [checked, setChecked] = useState(false);
    const [focus, setFocus] = useState(true);
    const before = useMemo(() => figure(base, transaction, false, focus), [base, transaction, focus]);
    const after = useMemo(() => figure(base, transaction, true, focus), [base, transaction, focus]);
    const intent = transaction.intent;
    const rebind = intent.kind === 'RebindInput';
    const activation = intent.kind === 'ReplaceActivation';
    const beforeValue = rebind ? intent.before?.variable ?? '未解析' : String(intent.before ?? '—');
    const afterValue = rebind ? intent.after?.variable ?? '未解析' : String(intent.after);
    const target = base.displayAliases[intent.nodeId] ?? transaction.beforeArchitecture?.nodes.find(n => n.id === intent.nodeId)?.label ?? intent.nodeId;
    const portName = rebind ? base.architecture.nodes.find(n => n.id === intent.nodeId)?.ports.find(p => p.id === intent.portId)?.name ?? '输入' : '';
    const runtime = transaction.runtimeVerification;
    const observed = runtime?.status === 'passed' && runtime.runtimeVerified;
    return _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { className: "review-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "review-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "SOURCE CHANGE REVIEW" }), _jsx("h2", { id: "review-title", children: rebind ? '审核连接修改' : activation ? '审核激活替换' : intent.kind === 'UpdateConfiguration' ? '审核配置修改' : '审核参数修改' })] }), _jsx("button", { className: "tool", onClick: onClose, disabled: busy, "aria-label": "\u5173\u95ED\u5BA1\u6838", children: _jsx(Icon, { name: "close" }) })] }), _jsxs("div", { className: "review-scope", children: [_jsx("b", { children: "Studio \u5DE5\u4F5C\u526F\u672C" }), _jsx("span", { children: statuses[transaction.status] ?? transaction.status }), _jsx("p", { children: "\u63D0\u4EA4\u5C06\u4FEE\u6539\u672C\u5730\u5DE5\u4F5C\u526F\u672C\u4E2D\u7684\u6E90\u7801\u3002\u5BFC\u5165\u524D\u7684\u539F\u59CB\u6587\u4EF6\u4E0D\u5728\u8FD9\u6B21\u4FEE\u6539\u8303\u56F4\u5185\u3002" })] }), _jsxs("div", { className: "change-summary", children: [_jsx("strong", { children: rebind ? `${target} · 输入连接` : activation ? `${target} · 激活函数` : intent.kind === 'UpdateConfiguration' ? `${intent.configurationName} · ${intent.parameter}` : intent.parameter }), _jsxs("span", { children: [beforeValue, " ", _jsx("b", { children: "\u2192" }), " ", afterValue] }), _jsxs("small", { children: [transaction.affectedNodeIds.length, " \u4E2A\u5BF9\u8C61\u53D7\u5F71\u54CD"] })] }), rebind && _jsxs("div", { className: "rebind-summary", children: [_jsxs("span", { children: ["\u76EE\u6807\u7AEF\u53E3\uFF1A", _jsx("code", { children: portName })] }), _jsxs("span", { children: ["\u6765\u6E90\uFF1A", intent.before && bindingLabel(base.architecture, base, intent.before), " \u2192 ", intent.after && bindingLabel(base.architecture, base, intent.after)] }), _jsxs("p", { children: ["\u6539\u63A5\u4F1A\u6539\u53D8\u76EE\u6807\u53CA\u4E0B\u6E38\u7684\u8BA1\u7B97\u884C\u4E3A\u3002", runtime ? '以冻结输入、模式和环境验证具体合同，并独立核对观察到的调用与连线。' : '兼容性仅为条件式符号签名，没有具体形状或运行时验证。'] })] }), !!transaction.blockers.length && _jsx("div", { className: "review-blockers", children: transaction.blockers.map((b, i) => _jsx("p", { children: b }, i)) }), before && after && _jsxs(_Fragment, { children: [_jsxs("div", { className: "review-view", children: [_jsx("span", { children: "\u524D\u540E\u67B6\u6784" }), _jsx("button", { className: focus ? 'active' : '', onClick: () => setFocus(true), children: "\u5F71\u54CD\u533A\u57DF" }), _jsx("button", { className: !focus ? 'active' : '', onClick: () => setFocus(false), children: "\u5B8C\u6574\u67B6\u6784" })] }), _jsxs("div", { className: "review-figures", children: [_jsxs("figure", { children: [_jsxs("figcaption", { children: ["\u4FEE\u6539\u524D \u00B7 ", beforeValue] }), _jsx("div", { dangerouslySetInnerHTML: { __html: before } })] }), _jsxs("figure", { children: [_jsxs("figcaption", { children: ["\u4FEE\u6539\u540E \u00B7 ", afterValue, _jsx("span", { children: rebind ? '橙色为改接连线与影响对象' : '橙色边框为受影响节点' })] }), _jsx("div", { dangerouslySetInnerHTML: { __html: after } })] })] })] }), _jsxs("div", { className: "review-columns", children: [_jsxs("section", { children: [_jsx("h3", { children: "\u6700\u5C0F\u6E90\u7801\u6539\u52A8" }), _jsx("pre", { className: "source-diff", children: transaction.diff || '没有可提交的源码 diff。' }), _jsxs("details", { children: [_jsx("summary", { children: "\u53D7\u5F71\u54CD\u7684\u5BF9\u8C61\u4E0E\u6765\u6E90" }), _jsx("ul", { children: transaction.affectedNodeIds.map(id => _jsxs("li", { children: [transaction.beforeArchitecture?.nodes.find(n => n.id === id)?.label ?? id, _jsx("code", { children: id })] }, id)) }), transaction.intent.origin && _jsxs("p", { children: [transaction.intent.origin.path, ":", transaction.intent.origin.line, " \u00B7 ", _jsx("code", { children: transaction.intent.origin.expression })] })] })] }), _jsxs("section", { children: [_jsx("h3", { children: "\u9A8C\u8BC1\u7ED3\u679C" }), _jsx("div", { className: "review-gates", children: transaction.gates.map(g => _jsxs("details", { children: [_jsxs("summary", { children: [_jsx("i", { className: g.status === 'passed' ? 'passed' : g.status === 'failed' ? 'failed' : 'pending' }), _jsx("span", { children: g.label }), _jsx("small", { children: g.status === 'passed' ? '通过' : g.status === 'failed' ? '失败' : '未执行' })] }), _jsx("p", { children: g.message })] }, g.id)) })] })] }), runtime && _jsxs("section", { className: "runtime-review", children: [_jsxs("h3", { children: ["\u9694\u79BB\u8FD0\u884C \u00B7 ", observed ? '已验证冻结样本' : '未通过'] }), _jsx("p", { children: runtime.reason ?? '运行范围限于明确声明的输入与模式，不要求改变前后数值相同。' }), runtime.observation?.modes.map(mode => _jsxs("div", { className: "runtime-mode", children: [_jsx("b", { children: mode.mode }), _jsxs("span", { children: [mode.calls.length, " \u6B21\u8C03\u7528"] }), _jsxs("span", { children: ["\u524D\u5411 ", mode.finite ? '有限' : '失败'] }), _jsxs("span", { children: ["\u68AF\u5EA6 ", mode.gradients.finite ? '有限' : '失败'] }), _jsxs("span", { children: ["\u7ED3\u6784\u91CD\u653E ", mode.replay.structureEqual && mode.replay.bindingsEqual ? '一致' : '失败'] })] }, mode.mode)), _jsxs("details", { children: [_jsx("summary", { children: "\u8F93\u5165\u3001\u9694\u79BB\u3001\u8D44\u6E90\u4E0E\u72B6\u6001\u8BC1\u636E" }), _jsx("pre", { children: JSON.stringify({ manifest: runtime.manifest, stateCompatibility: runtime.stateCompatibility, observations: runtime.observation, limitations: runtime.limitations }, null, 2) })] })] }), _jsxs("p", { className: "review-note", children: [runtime ? observed ? '模型在隔离 CPU 环境中执行；通过只覆盖冻结样本，不证明任意输入或新旧数值等价。' : '必需运行验证未通过，不能批准或提交。' : '模型未被执行；没有运行时或数值等价性验证。', " ", transaction.checkpointImpact.message, " \u63D0\u4EA4\u540E\u4FDD\u7559\u80FD\u552F\u4E00\u5BF9\u5E94\u7684\u8282\u70B9\u6837\u5F0F\u4E0E\u4F4D\u7F6E\uFF1B\u7ED1\u5B9A\u6539\u53D8\u7684\u8FDE\u7EBF\u91CD\u65B0\u4F7F\u7528\u9ED8\u8BA4\u6837\u5F0F\u3002"] }), rebind && intent.contract && _jsxs("details", { className: "review-binding", children: [_jsx("summary", { children: "\u8F93\u5165\u5951\u7EA6\u4E0E\u6761\u4EF6" }), _jsx("p", { children: intent.contract.condition }), _jsxs("p", { children: ["\u7AEF\u53E3\uFF1A", _jsx("code", { children: intent.portId })] }), Array.isArray(intent.contract.shape) ? _jsxs("p", { children: ["\u5F62\u72B6\uFF1A", _jsxs("code", { children: ["[", intent.contract.shape.join(', '), "]"] }), " \u00B7 \u7C7B\u578B\uFF1A", _jsx("code", { children: String(intent.contract.dtype) })] }) : _jsx("p", { children: "\u517C\u5BB9\u6027\u4E3A\u6761\u4EF6\u5F0F\u7B26\u53F7\u7B7E\u540D\u3002" })] }), _jsxs("details", { className: "review-binding", children: [_jsx("summary", { children: "\u67E5\u770B\u7248\u672C\u7ED1\u5B9A" }), _jsxs("p", { children: ["\u6E90\u7801\uFF1A", _jsx("code", { children: transaction.sourceDigest })] }), _jsxs("p", { children: ["\u5BA1\u6838\uFF1A", _jsx("code", { children: transaction.reviewDigest ?? '无' })] })] }), error && _jsx("p", { className: "error-text", role: "alert", children: error }), _jsxs("div", { className: "review-actions", children: [transaction.status === 'ReviewReady' && _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: checked, onChange: e => setChecked(e.target.checked) }), "\u6211\u5DF2\u6838\u5BF9\u6539\u52A8\u3001\u5F71\u54CD\u8303\u56F4\u4E0E\u9A8C\u8BC1\u7ED3\u679C"] }), _jsx("button", { onClick: onClose, disabled: busy, children: transaction.status === 'Committed' ? '完成' : '取消' }), transaction.status === 'ReviewReady' && _jsx("button", { className: "primary", disabled: !checked || busy, onClick: onApprove, children: "\u6279\u51C6\u8FD9\u4EFD\u4FEE\u6539" }), transaction.status === 'Approved' && _jsx("button", { className: "primary", disabled: busy, onClick: onCommit, children: "\u63D0\u4EA4\u5230\u5DE5\u4F5C\u526F\u672C" })] })] }) });
}
