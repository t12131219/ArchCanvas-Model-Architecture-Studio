import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
export function ConnectionEditor({ document, nodeId, portId: initialPortId, enabled, busy, inputSpec, onSetup, onInspect, onPrepare }) {
    const ports = document.architecture.nodes.find(n => n.id === nodeId)?.ports.filter(p => p.direction === 'in') ?? [];
    const [portId, setPort] = useState(initialPortId);
    const [options, setOptions] = useState(null);
    const [candidate, setCandidate] = useState('');
    const [error, setError] = useState('');
    useEffect(() => { setOptions(null); setCandidate(''); setError(''); }, [portId]);
    const edge = document.architecture.edges.find(e => e.target.nodeId === nodeId && e.target.portId === portId);
    const portName = document.architecture.nodes.find(n => n.id === nodeId)?.ports.find(p => p.id === portId)?.name ?? '输入';
    const label = (binding) => binding ? bindingLabel(document.architecture, document, binding) : '未解析';
    const selected = options?.candidates.find(c => `${c.binding.nodeId}:${c.binding.portId}` === candidate);
    const current = options?.target?.currentBinding;
    const unchanged = selected && current && selected.binding.nodeId === current.nodeId && selected.binding.portId === current.portId;
    async function inspect() {
        setError('');
        try {
            const result = await onInspect(nodeId, portId);
            setOptions(result);
            const first = result.candidates.find(c => c.binding.nodeId !== result.target?.currentBinding.nodeId || c.binding.portId !== result.target?.currentBinding.portId);
            setCandidate(first ? `${first.binding.nodeId}:${first.binding.portId}` : '');
        }
        catch (e) {
            setError(String(e));
        }
    }
    return _jsxs("section", { className: "property-section semantic-editor connection-editor", children: [_jsxs("h3", { children: ["\u8F93\u5165\u8FDE\u63A5", _jsx("span", { className: "review-tag", children: "\u5148\u5BA1\u6838" })] }), ports.length > 1 && _jsxs(_Fragment, { children: [_jsx("label", { className: "field-label", htmlFor: "rebind-target-port", children: "\u76EE\u6807\u8F93\u5165\u7AEF\u53E3" }), _jsx("select", { id: "rebind-target-port", "aria-label": "\u76EE\u6807\u8F93\u5165\u7AEF\u53E3", className: "field-select", value: portId, onChange: e => setPort(e.target.value), disabled: busy, children: ports.map(p => _jsx("option", { value: p.id, children: p.name }, p.id)) })] }), _jsxs("div", { className: "binding-card", children: [_jsxs("small", { children: ["\u5F53\u524D\u6765\u6E90 \u00B7 ", portName] }), _jsx("strong", { children: label(edge ? { ...edge.source, tensorId: edge.tensorId } : undefined) })] }), _jsx("button", { className: "full-button", onClick: onSetup, disabled: busy, children: inputSpec ? '调整运行输入与模式' : '设置运行输入与模式' }), inputSpec && _jsxs("p", { className: "field-help", children: ["CPU \u00B7 ", inputSpec.modes.join(' / '), " \u00B7 \u968F\u673A\u79CD\u5B50 ", inputSpec.seed] }), _jsx("button", { className: "full-button", disabled: !enabled || busy || !inputSpec, onClick: () => void inspect(), children: options ? '重新检查可选来源' : '检查连接编辑能力' }), options && _jsxs(_Fragment, { children: [options.target && _jsxs("p", { className: "field-help", children: ["\u6E90\u7801\u8F93\u5165\uFF1A", _jsx("code", { children: options.target.slot.variable }), " \u00B7 ", options.target.slot.path, ":", options.target.slot.line] }), options.supported && options.candidates.length > 0 && _jsxs(_Fragment, { children: [_jsx("label", { className: "field-label", htmlFor: "rebind-producer", children: "\u65B0\u7684\u8F93\u5165\u6765\u6E90" }), _jsxs("select", { id: "rebind-producer", "aria-label": "\u65B0\u7684\u8F93\u5165\u6765\u6E90", className: "field-select", value: candidate, disabled: busy, onChange: e => setCandidate(e.target.value), children: [_jsx("option", { value: "", disabled: true, children: "\u9009\u62E9\u53EF\u7528\u6765\u6E90" }), options.candidates.map(c => _jsxs("option", { value: `${c.binding.nodeId}:${c.binding.portId}`, children: [label(c.binding), " \u00B7 ", c.variable, c.binding.nodeId === current?.nodeId && c.binding.portId === current.portId ? '（当前）' : ''] }, `${c.binding.nodeId}:${c.binding.portId}`))] }), _jsx("p", { className: "field-help", children: "\u6765\u6E90\u5728\u8C03\u7528\u524D\u5DF2\u5B9A\u4E49\u3002\u9884\u89C8\u4F1A\u5728\u9694\u79BB\u73AF\u5883\u4E2D\u9A8C\u8BC1\u8F93\u5165\u5408\u540C\u3001\u524D\u5411\u3001\u68AF\u5EA6\u548C\u72B6\u6001\uFF1B\u6539\u63A5\u4F1A\u6539\u53D8\u8BA1\u7B97\u884C\u4E3A\u3002" }), selected && _jsxs("details", { className: "connection-contract", children: [_jsx("summary", { children: "\u517C\u5BB9\u6027\u6761\u4EF6" }), _jsx("p", { children: selected.contract.condition }), _jsx("code", { children: Array.isArray(selected.contract.shape) ? `[${selected.contract.shape.join(', ')}] · ${selected.contract.dtype}` : '符号签名' })] }), _jsx("button", { className: "full-button", disabled: busy || !selected || !!unchanged || !inputSpec, onClick: () => selected && onPrepare(nodeId, portId, selected.binding), children: "\u8FD0\u884C\u9A8C\u8BC1\u5E76\u9884\u89C8\u8FDE\u63A5\u4FEE\u6539" })] }), (!options.supported || !options.candidates.length) && _jsx("p", { className: "field-help", children: _jsx("b", { children: "\u8FDE\u63A5\u63D0\u6848\u6682\u4E0D\u53EF\u63D0\u4EA4" }) }), !!options.blockers.length && _jsx("div", { className: "connection-blockers", children: options.blockers.map((b, i) => _jsx("p", { children: b }, i)) })] }), !options && _jsx("p", { className: "field-help", children: "\u5148\u767B\u8BB0\u660E\u786E\u7684\u8F93\u5165\u4E0E\u6A21\u5F0F\u3002\u5019\u9009\u68C0\u67E5\u4FDD\u6301\u9759\u6001\uFF1B\u8FDE\u63A5\u9884\u89C8\u624D\u6267\u884C\u9694\u79BB\u9A8C\u8BC1\uFF0C\u6240\u6709\u5FC5\u9700\u95E8\u901A\u8FC7\u540E\u624D\u80FD\u5BA1\u6838\u63D0\u4EA4\u3002" }), error && _jsx("p", { className: "error-text", role: "alert", children: error })] });
}
export function bindingLabel(architecture, document, binding) {
    const node = architecture.nodes.find(n => n.id === binding.nodeId);
    return document.displayAliases[binding.nodeId] ?? node?.label ?? binding.nodeId;
}
