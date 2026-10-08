import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-QGqYO6/icons.mjs';
export function RuntimeProfileDialog({ architecture, initial, example, onSave, onClose }) {
    const names = architecture.nodes.filter(n => n.kind === 'Input').map(n => n.label);
    const demo = { query: { shape: [2, 3, 8], dtype: 'float32' }, memory: { shape: [2, 5, 8], dtype: 'float32' }, alternative: { shape: [2, 5, 8], dtype: 'float32' }, padding_mask: { shape: [2, 5], dtype: 'bool' } };
    const [draft, setDraft] = useState(JSON.stringify(initial?.inputs ?? (example ? demo : Object.fromEntries(names.map(name => [name, { shape: [], dtype: 'float32' }]))), null, 2));
    const [constructor, setConstructor] = useState(JSON.stringify(initial?.constructor ?? {}, null, 2));
    const [seed, setSeed] = useState(String(initial?.seed ?? 0));
    const [evalMode, setEval] = useState(initial?.modes.includes('eval') ?? true);
    const [trainMode, setTrain] = useState(initial?.modes.includes('train') ?? true);
    const [error, setError] = useState('');
    function save() {
        try {
            const inputs = JSON.parse(draft);
            if (!inputs || typeof inputs !== 'object' || Array.isArray(inputs) || Object.keys(inputs).sort().join('|') !== [...names].sort().join('|'))
                throw new Error('请为每个源码输入填写一份形状和类型，名称须完全一致。');
            for (const input of Object.values(inputs))
                if (!Array.isArray(input.shape) || !input.shape.length || input.shape.some(d => !Number.isInteger(d) || d < 1) || typeof input.dtype !== 'string')
                    throw new Error('shape 必须是正整数数组，dtype 必须明确填写。');
            const constructorValues = JSON.parse(constructor);
            if (!constructorValues || typeof constructorValues !== 'object' || Array.isArray(constructorValues))
                throw new Error('构造参数须为 JSON 对象。');
            if (Object.keys(constructorValues).length)
                throw new Error('当前验证合同仅支持源码中的默认构造参数，请保留 {}。');
            if (!Number.isSafeInteger(Number(seed)) || Number(seed) < 0 || !evalMode && !trainMode)
                throw new Error('填写非负整数随机种子，并至少选择一种运行模式。');
            onSave({ schemaVersion: 1, inputs, seed: Number(seed), modes: [...(evalMode ? ['eval'] : []), ...(trainMode ? ['train'] : [])], constructor: constructorValues });
        }
        catch (e) {
            setError(String(e));
        }
    }
    return _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { className: "runtime-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "runtime-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "ISOLATED CPU VALIDATION" }), _jsx("h2", { id: "runtime-title", children: "\u8FDE\u63A5\u9A8C\u8BC1\u7684\u8F93\u5165\u4E0E\u6A21\u5F0F" })] }), _jsx("button", { className: "tool", "aria-label": "\u5173\u95ED\u8FD0\u884C\u8BBE\u7F6E", onClick: onClose, children: _jsx(Icon, { name: "close" }) })] }), _jsxs("p", { className: "runtime-intro", children: ["\u4E3A ", architecture.label, " \u660E\u786E\u8F93\u5165\u3002\u9884\u89C8\u8BED\u4E49\u4FEE\u6539\u65F6\uFF0C\u5C06\u5728\u9694\u79BB CPU worker \u4E2D\u8FD0\u884C\u5019\u9009\u6E90\u7801\uFF0C\u6838\u5BF9\u4ECE\u5F53\u524D\u6E90\u7801\u4E0E\u4FEE\u6539\u610F\u56FE\u72EC\u7ACB\u63A8\u5BFC\u7684\u8C03\u7528\u3001\u5F62\u72B6\u3001\u7C7B\u578B\u548C\u72B6\u6001\u9884\u671F\u3002\u73B0\u5728\u4FDD\u5B58\u8BBE\u7F6E\u53EA\u767B\u8BB0\u8F93\u5165\uFF0C\u4E0D\u6267\u884C\u6A21\u578B\u3002"] }), example && _jsx("p", { className: "field-help", children: "\u4EE5\u4E0B\u662F\u8FD9\u4E2A\u793A\u4F8B\u7684\u6F14\u793A\u8F93\u5165\uFF0C\u53EF\u4FEE\u6539\uFF1B\u5B83\u4EEC\u4E0D\u662F\u81EA\u52A8\u63A8\u65AD\u7684\u5B9E\u9645\u8BAD\u7EC3\u8F93\u5165\u3002" }), _jsxs("label", { className: "field-label", htmlFor: "runtime-inputs", children: ["\u5177\u540D\u8F93\u5165 \u00B7 ", names.join('、')] }), _jsx("textarea", { id: "runtime-inputs", "aria-label": "\u8FD0\u884C\u8F93\u5165 JSON", value: draft, onChange: e => setDraft(e.target.value), spellCheck: false }), _jsxs("div", { className: "runtime-fields", children: [_jsxs("label", { children: ["\u968F\u673A\u79CD\u5B50", _jsx("input", { "aria-label": "\u8FD0\u884C\u968F\u673A\u79CD\u5B50", type: "number", min: "0", value: seed, onChange: e => setSeed(e.target.value) })] }), _jsxs("label", { className: "check-field", children: [_jsx("input", { type: "checkbox", checked: evalMode, onChange: e => setEval(e.target.checked) }), "\u8BC4\u4F30\u6A21\u5F0F eval"] }), _jsxs("label", { className: "check-field", children: [_jsx("input", { type: "checkbox", checked: trainMode, onChange: e => setTrain(e.target.checked) }), "\u8BAD\u7EC3\u6A21\u5F0F train"] })] }), _jsxs("details", { children: [_jsx("summary", { children: "\u6A21\u578B\u6784\u9020\u53C2\u6570" }), _jsxs("p", { className: "field-help", children: ["\u5F53\u524D\u5408\u540C\u4F7F\u7528\u6E90\u7801\u4E2D\u7684\u9ED8\u8BA4\u6784\u9020\u53C2\u6570\uFF0C\u987B\u4FDD\u7559 ", '{}', "\uFF1B\u4E0D\u52A0\u8F7D checkpoint\u3002"] }), _jsx("textarea", { "aria-label": "\u6A21\u578B\u6784\u9020\u53C2\u6570 JSON", className: "constructor-input", value: constructor, onChange: e => setConstructor(e.target.value), spellCheck: false })] }), _jsx("p", { className: "review-note", children: "\u9ED8\u8BA4\u7981\u7F51\u3001\u53EA\u8BFB\u6E90\u7801\u3001\u72EC\u7ACB\u4E34\u65F6\u5199\u5165\u76EE\u5F55\uFF0C\u5E76\u9650\u5236\u65F6\u95F4\u548C\u8D44\u6E90\u3002\u7F3A\u5C11\u5DF2\u9A8C\u8BC1\u9694\u79BB\u73AF\u5883\u6216\u6240\u9700\u8FD0\u884C\u68C0\u67E5\u5931\u8D25\u65F6\uFF0C\u8FDE\u63A5\u63D0\u6848\u65E0\u6CD5\u63D0\u4EA4\u3002\u6837\u672C\u68C0\u67E5\u4E0D\u8BC1\u660E\u5168\u7A0B\u5E8F\u6216\u6570\u503C\u7B49\u4EF7\u3002" }), error && _jsx("p", { role: "alert", className: "error-text", children: error }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: onClose, children: "\u53D6\u6D88" }), _jsx("button", { className: "primary", onClick: save, children: "\u4FDD\u5B58\u8F93\u5165\u8BBE\u7F6E" })] })] }) });
}
