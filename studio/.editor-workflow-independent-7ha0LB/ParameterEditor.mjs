import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
export function ParameterEditor({ node, busy, enabled, onPrepare, onInspectConfiguration }) {
    const parameter = node.kind === 'Dropout' ? 'p' : node.kind === 'MultiheadAttention' ? 'dropout' : undefined;
    const origin = parameter ? node.parameterOrigins?.[parameter] : undefined;
    const value = parameter ? node.parameters[parameter] : undefined;
    const [draft, setDraft] = useState(String(value ?? ''));
    const [configuration, setConfiguration] = useState(null);
    const [error, setError] = useState('');
    useEffect(() => { setDraft(String(value ?? '')); setConfiguration(null); setError(''); }, [node.id, value]);
    if (!parameter)
        return null;
    const literal = origin?.kind === 'literal' && /[.eE]/.test(origin.expression);
    const editable = enabled && (literal || configuration?.supported) && typeof value === 'number';
    const numeric = Number(draft);
    return _jsxs("section", { className: "property-section semantic-editor", children: [_jsxs("h3", { children: ["\u53C2\u6570\u4FEE\u6539", _jsx("span", { className: "review-tag", children: "\u5148\u5BA1\u6838" })] }), _jsxs("label", { className: "field-label", htmlFor: "probability", children: [parameter, " \u00B7 \u5F53\u524D ", String(value)] }), _jsxs("div", { className: "probability-input", children: [_jsx("input", { id: "probability", "aria-label": "\u65B0\u7684 Dropout \u6982\u7387", type: "number", min: "0", max: "1", step: "0.05", value: draft, disabled: !editable || busy, onChange: e => setDraft(e.target.value) }), _jsx("button", { onClick: () => onPrepare(parameter, numeric, !literal), disabled: !editable || busy || !draft.trim() || !Number.isFinite(numeric) || numeric < 0 || numeric > 1 || numeric === value, children: "\u9884\u89C8\u4FEE\u6539" })] }), origin && _jsxs("p", { className: "field-help", children: ["\u6765\u6E90\uFF1A", origin.path, ":", origin.line, _jsx("br", {}), _jsx("code", { children: origin.expression }), " \u00B7 ", origin.kind === 'literal' ? '源码字面量' : origin.kind === 'constructor_argument' ? '构造参数' : '派生或未知表达式'] }), !literal && _jsx("button", { disabled: !enabled || busy, onClick: async () => { setError(''); try {
                    setConfiguration(await onInspectConfiguration(parameter));
                }
                catch (e) {
                    setError(String(e));
                } }, children: "\u68C0\u67E5\u914D\u7F6E\u6765\u6E90\u4E0E\u5F71\u54CD" }), configuration?.target && _jsxs("p", { className: "field-help", children: ["\u914D\u7F6E\uFF1A", _jsx("code", { children: configuration.target.name }), " \u00B7 ", configuration.target.origin.path, ":", configuration.target.origin.line, _jsx("br", {}), "\u5171 ", configuration.affectedNodeIds.length, " \u4E2A\u8C03\u7528\u53D7\u5F71\u54CD\uFF1B\u4FEE\u6539\u552F\u4E00\u914D\u7F6E\u503C\uFF0C\u4FDD\u7559\u8BFB\u53D6\u8868\u8FBE\u5F0F\u3002"] }), configuration?.blockers.map((blocker, i) => _jsx("p", { className: "field-help", children: blocker }, i)), error && _jsx("p", { role: "alert", className: "error-text", children: error }), _jsx("p", { className: "field-help", children: editable ? '修改 Studio 工作副本。预览会列出共享这一来源的全部调用；审核通过后才能提交。' : '支持浮点字面量及唯一模块常量，配置的全部读取须为已注册概率参数。派生表达式和未证明影响范围保留为提案。' })] });
}
