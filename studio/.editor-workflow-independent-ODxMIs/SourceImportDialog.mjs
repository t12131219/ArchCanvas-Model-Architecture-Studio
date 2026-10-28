import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef, useState } from 'react';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-ODxMIs/icons.mjs';
import { useModalFocus } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-ODxMIs/WorkspaceUI.mjs';
export function SourceImportDialog(props) {
    const panel = useModalFocus(props.onClose);
    const file = useRef(null);
    const [tab, setTab] = useState('code');
    const [loaded, setLoaded] = useState('');
    return _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { ref: panel, className: "import-modal source-import", role: "dialog", "aria-modal": "true", "aria-labelledby": "import-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("h2", { id: "import-title", children: "\u6253\u5F00\u6A21\u578B" }), _jsx("p", { children: "\u4ECE\u6E90\u7801\u5EFA\u7ACB\u6A21\u578B\u89C6\u56FE\uFF0C\u6216\u6062\u590D\u5DF2\u4FDD\u5B58\u7684\u6587\u6863\u3002" })] }), _jsx("button", { className: "tool", onClick: props.onClose, "aria-label": "\u5173\u95ED\u5BFC\u5165", children: _jsx(Icon, { name: "close" }) })] }), _jsxs("div", { className: "import-tabs", role: "tablist", "aria-label": "\u5BFC\u5165\u65B9\u5F0F", children: [_jsx("button", { role: "tab", id: "import-code-tab", "aria-controls": "import-code", "aria-selected": tab === 'code', onClick: () => setTab('code'), children: "Python \u5355\u6587\u4EF6" }), _jsx("button", { role: "tab", id: "import-project-tab", "aria-controls": "import-project", "aria-selected": tab === 'project', onClick: () => setTab('project'), children: "\u5DE5\u7A0B\u76EE\u5F55 / \u5DF2\u6709\u6587\u6863" })] }), _jsx("input", { ref: file, hidden: true, type: "file", accept: ".py,.json", "aria-label": "\u9009\u62E9\u6E90\u6587\u4EF6", onChange: async (event) => {
                        const chosen = event.target.files?.[0];
                        if (!chosen)
                            return;
                        try {
                            const json = chosen.name.toLowerCase().endsWith('.json');
                            if (chosen.size > (json ? 16_000_000 : 2_000_000))
                                throw new Error(json ? '编辑 JSON 超过 16 MB' : 'Python 源码超过 2 MB');
                            const text = await chosen.text();
                            if (json)
                                await props.onJson(text);
                            else {
                                props.onSource(text);
                                props.onFilename(chosen.name);
                                setLoaded(chosen.name);
                                setTab('code');
                                props.onError('');
                            }
                        }
                        catch (error) {
                            props.onError(`导入失败：${String(error)}`);
                        }
                        event.target.value = '';
                    } }), tab === 'code' ? _jsxs("section", { role: "tabpanel", id: "import-code", "aria-labelledby": "import-code-tab", children: [_jsxs("div", { className: "import-file-row", children: [_jsxs("button", { onClick: () => file.current?.click(), children: [_jsx(Icon, { name: "file", size: 15 }), "\u9009\u62E9 .py \u6587\u4EF6"] }), _jsx("span", { role: "status", children: loaded || '也可以在下方粘贴源码' })] }), _jsxs("div", { className: "import-fields", children: [_jsxs("label", { children: ["\u6A21\u578B\u5165\u53E3", _jsx("input", { "aria-label": "\u6A21\u578B\u5165\u53E3\u7C7B\u540D", value: props.entry, placeholder: "\u4F8B\u5982 Model", onChange: event => props.onEntry(event.target.value) }), _jsx("small", { children: "\u6E90\u7801\u4E2D\u7684 nn.Module \u7C7B\u540D" })] }), _jsxs("label", { children: ["\u6E90\u6587\u4EF6\u540D", _jsx("input", { "aria-label": "\u6E90\u6587\u4EF6\u540D", value: props.filename, placeholder: "model.py", onChange: event => props.onFilename(event.target.value) }), _jsx("small", { children: "\u7528\u4E8E\u4FDD\u5B58\u6E90\u7801\u4F4D\u7F6E" })] })] }), _jsxs("label", { className: "import-code-label", htmlFor: "import-source-code", children: ["Python \u6E90\u7801 ", _jsx("span", { children: "\u9759\u6001\u5206\u6790 \u00B7 \u4E0D\u6267\u884C\u6A21\u578B" })] }), _jsx("textarea", { id: "import-source-code", "aria-label": "Python \u6E90\u7801", spellCheck: false, placeholder: 'import torch\nfrom torch import nn\n\nclass Model(nn.Module):\n    ...', value: props.source, onChange: event => props.onSource(event.target.value) })] }) : _jsxs("section", { role: "tabpanel", id: "import-project", "aria-labelledby": "import-project-tab", className: "import-project-options", children: [_jsx(Icon, { name: "layers", size: 28 }), _jsx("h3", { children: "\u6253\u5F00\u5B8C\u6574\u5DE5\u7A0B\u6216\u6062\u590D\u6587\u6863" }), _jsx("p", { children: "\u9009\u62E9\u591A\u4E2A Python \u6587\u4EF6\u6216\u6E90\u7801\u76EE\u5F55\uFF0C\u626B\u63CF\u6A21\u578B\u4E0E\u5305\u542B\u5C42\u7EA7\u540E\u9009\u62E9\u5165\u53E3\u3002\u4E5F\u53EF\u8F7D\u5165 Summary \u539F\u751F\u6587\u6863\u3001\u8BED\u4E49\u753B\u5E03\u3001\u67B6\u6784\u6587\u6863\u3001authoring \u6587\u6863\u3001IR\u3001\u7F16\u8F91 JSON \u6216\u6E90\u7801\u9002\u914D\u5305\u3002" }), _jsxs("button", { onClick: () => file.current?.click(), children: [_jsx(Icon, { name: "file", size: 16 }), "\u9009\u62E9 Summary / \u7F16\u8F91 JSON"] }), _jsxs("button", { onClick: props.onProject, children: [_jsx(Icon, { name: "file", size: 16 }), "\u9009\u62E9\u6E90\u7801\u76EE\u5F55\u6216\u591A\u4E2A\u6587\u4EF6"] }), _jsx("small", { children: "\u6E90\u7801\uFF1A\u6700\u591A 80 \u4E2A\u6587\u4EF6 / 2 MB \u00B7 \u6587\u6863 JSON\uFF1A16 MB" })] }), props.error && _jsx("p", { className: "import-error", role: "alert", children: props.error }), _jsxs("div", { className: "modal-actions", children: [_jsx("span", { children: props.busy ? '正在静态分析…' : '原始源码保持不变' }), _jsx("button", { onClick: props.onClose, children: "\u53D6\u6D88" }), tab === 'code' && _jsx("button", { className: "primary", onClick: props.onAnalyze, disabled: props.busy || !props.source.trim() || !props.entry.trim() || !props.filename.trim(), children: props.busy ? '分析中…' : '分析并打开' })] })] }) });
}
