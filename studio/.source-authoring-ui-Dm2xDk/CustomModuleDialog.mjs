import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef, useState } from 'react';
import { api } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/api.ts';
import { Icon } from './icons.mjs';
import { readCustomModuleDefinition } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/customModules.ts';
const EXAMPLE = `from torch import nn

class CustomBlock(nn.Module):
    def __init__(self, width=16):
        super().__init__()
        self.project = nn.Linear(width, width)
        self.activation = nn.Tanh()

    def forward(self, x):
        return self.activation(self.project(x))
`;
export function CustomModuleDialog({ onClose, onInsert }) {
    const [source, setSource] = useState(EXAMPLE), [entry, setEntry] = useState('CustomBlock'), [label, setLabel] = useState('我的源码模块');
    const [constructorText, setConstructorText] = useState('{"width": 16}');
    const [preview, setPreview] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
    const inFlight = useRef(false);
    function change(update) { update(); setPreview(null); setError(''); }
    async function inspect() {
        if (inFlight.current)
            return;
        inFlight.current = true;
        setBusy(true);
        setError('');
        setPreview(null);
        try {
            const constructorValues = JSON.parse(constructorText);
            if (!constructorValues || typeof constructorValues !== 'object' || Array.isArray(constructorValues))
                throw new Error('构造参数应为 JSON 对象，如 {"width":16}');
            const result = await api.previewCustomModule({ source, entry, label, constructorValues });
            readCustomModuleDefinition(result.definition);
            setPreview(result);
        }
        catch (reason) {
            setError(String(reason));
        }
        finally {
            inFlight.current = false;
            setBusy(false);
        }
    }
    return _jsx("div", { className: "modal-backdrop", children: _jsxs("section", { className: "custom-source-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "custom-source-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "CUSTOM SOURCE MODULE" }), _jsx("h2", { id: "custom-source-title", children: "\u7528\u6E90\u7801\u521B\u5EFA\u6A21\u5757" })] }), _jsx("button", { disabled: busy, "aria-label": "\u5173\u95ED\u6E90\u7801\u6A21\u5757\u7A97\u53E3", onClick: onClose, children: _jsx(Icon, { name: "close" }) })] }), _jsx("p", { children: "\u7F16\u5199\u4E00\u4E2A nn.Module \u7C7B\uFF0C\u9759\u6001\u9884\u89C8\u540E\u52A0\u5165\u5F53\u524D\u6A21\u578B\u3002\u6A21\u5757\u53EF\u4EE5\u91CD\u590D\u62D6\u5165\uFF0C\u6E90\u7801\u548C\u6784\u9020\u53C2\u6570\u968F\u8349\u7A3F\u4FDD\u5B58\u3002" }), _jsxs("div", { className: "custom-module-fields", children: [_jsxs("label", { children: ["\u7C7B\u540D", _jsx("input", { "aria-label": "\u81EA\u5B9A\u4E49\u6A21\u5757\u7C7B\u540D", disabled: busy, value: entry, onChange: event => change(() => setEntry(event.target.value)) })] }), _jsxs("label", { children: ["\u663E\u793A\u540D\u79F0", _jsx("input", { "aria-label": "\u81EA\u5B9A\u4E49\u6A21\u5757\u663E\u793A\u540D\u79F0", disabled: busy, value: label, onChange: event => change(() => setLabel(event.target.value)) })] })] }), _jsx("textarea", { "aria-label": "\u81EA\u5B9A\u4E49\u6A21\u5757 Python \u6E90\u7801", className: "custom-source-editor", spellCheck: false, disabled: busy, value: source, onChange: event => change(() => setSource(event.target.value)) }), _jsxs("label", { className: "custom-source-label", children: ["\u6784\u9020\u53C2\u6570\uFF08JSON \u5BF9\u8C61\uFF09", _jsx("textarea", { "aria-label": "\u81EA\u5B9A\u4E49\u6A21\u5757\u6784\u9020\u53C2\u6570", className: "custom-constructor", spellCheck: false, disabled: busy, value: constructorText, onChange: event => change(() => setConstructorText(event.target.value)) })] }), error && _jsx("p", { className: "error-text", role: "alert", children: error }), preview && _jsxs("div", { className: "custom-contract", role: "status", children: [_jsxs("b", { children: [preview.module.label, " \u00B7 ", preview.definition.entry] }), _jsx("div", { className: "custom-port-list", children: preview.module.ports.map(port => _jsxs("code", { children: [port.direction === 'in' ? '输入' : '输出', " ", port.name] }, port.id)) }), _jsx("p", { children: "\u4EC5\u89E3\u6790\u6E90\u7801\uFF0C\u672A\u6267\u884C\u6A21\u578B\uFF1B\u8F93\u51FA\u5F62\u72B6\u4FDD\u7559\u4E3A\u672A\u77E5\u3002\u591A\u8F93\u51FA\u5C06\u6309\u9759\u6001\u8FD4\u56DE\u8DEF\u5F84\u8FDE\u63A5\u3002" }), preview.architecture.diagnostics.filter(item => item.level !== 'info').map((item, index) => _jsx("p", { children: item.message }, index)), _jsxs("details", { children: [_jsxs("summary", { children: ["\u9759\u6001\u7ED3\u6784 \u00B7 ", preview.architecture.nodes.length, " \u4E2A\u4E8B\u5B9E\u5BF9\u8C61"] }), _jsx("pre", { children: preview.architecture.nodes.map(node => `${node.label} · ${node.kind} · ${node.evidence}`).join('\n') })] })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { disabled: busy, onClick: onClose, children: "\u53D6\u6D88" }), _jsx("button", { disabled: busy || !source.trim() || !entry.trim(), onClick: () => void inspect(), children: busy ? '正在静态预览…' : '静态预览' }), _jsx("button", { className: "primary", disabled: busy || !preview, onClick: () => { if (preview)
                                onInsert(preview); }, children: "\u6DFB\u52A0\u5230\u6A21\u578B" })] })] }) });
}
