import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function ActivationEditor({ node, enabled, busy, inputSpec, onSetup, onPrepare }) {
    if (!['ReLU', 'GELU'].includes(node.kind))
        return null;
    const next = node.kind === 'ReLU' ? 'GELU' : 'ReLU';
    return _jsxs("section", { className: "property-section semantic-editor", children: [_jsxs("h3", { children: ["\u6FC0\u6D3B\u51FD\u6570", _jsx("span", { className: "review-tag", children: "\u5148\u5BA1\u6838" })] }), _jsxs("p", { className: "field-help", children: ["\u5F53\u524D ", node.kind, " \u2192 ", next, "\u3002\u4EC5\u652F\u6301\u76F4\u63A5\u3001\u65E0\u53C2\u6570\u7684\u6784\u9020\uFF1B\u66FF\u6362\u4F1A\u6539\u53D8\u8BA1\u7B97\u6570\u503C\uFF0C\u4FDD\u7559\u8C03\u7528\u8FDE\u7EBF\u4E0E\u5F20\u91CF\u5408\u540C\u3002"] }), _jsx("button", { disabled: busy, onClick: onSetup, children: inputSpec ? '调整运行输入与模式' : '设置运行输入与模式' }), _jsx("button", { disabled: busy || !enabled || !inputSpec, onClick: () => onPrepare(next), children: "\u8FD0\u884C\u9A8C\u8BC1\u5E76\u9884\u89C8\u6FC0\u6D3B\u66FF\u6362" })] });
}
