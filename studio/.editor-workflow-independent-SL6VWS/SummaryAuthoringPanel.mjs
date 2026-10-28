import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
/** Retain Studio's inspector sections; the iframe alone owns editable facts. */
export function SummaryAuthoringPanel({ snapshot, selected, disabled, onEdit, onFormal, onCompile, onCertify }) {
    const state = snapshot?.authoring;
    const [pending, setPending] = useState(false), [error, setError] = useState('');
    const [presets, setPresets] = useState([]), [query, setQuery] = useState('');
    const [name, setName] = useState('自定义组合'), [from, setFrom] = useState(''), [to, setTo] = useState(''), [replace, setReplace] = useState(false);
    const [label, setLabel] = useState(''), [fields, setFields] = useState('{}');
    const [edgeId, setEdgeId] = useState('');
    const [modelTitle, setModelTitle] = useState(state?.title ?? '');
    const [moduleSource, setModuleSource] = useState('from torch import nn\nclass CustomBlock(nn.Module):\n def __init__(self, width=8):\n  super().__init__()\n  self.linear=nn.Linear(width,width)\n def forward(self,x):\n  return self.linear(x)\n');
    const [moduleEntry, setModuleEntry] = useState('CustomBlock'), [moduleConfig, setModuleConfig] = useState('{"width":8}');
    const [recipeAtomic, setRecipeAtomic] = useState(false);
    const chosen = state?.nodes.filter(n => selected.includes(n.id)) ?? [], node = chosen.length === 1 ? chosen[0] : undefined;
    useEffect(() => {
        setLabel(node?.label ?? '');
        setFields(JSON.stringify({ constructor: node && Object.hasOwn(node, 'constructor') ? node.constructor : {}, arguments: node?.arguments ?? {} }, null, 2));
    }, [node?.id, node?.label, JSON.stringify(node?.constructor), JSON.stringify(node?.arguments)]);
    useEffect(() => setModelTitle(state?.title ?? ''), [state?.title]);
    useEffect(() => { if (node?.module) {
        setModuleSource(node.module.source);
        setModuleEntry(node.module.entry);
        setModuleConfig(JSON.stringify(node.module.constructor, null, 2));
    } }, [node?.id, node?.module?.source, JSON.stringify(node?.module?.constructor)]);
    useEffect(() => {
        let live = true;
        void fetch('/preview/data/semantic/authoring-presets.json').then(r => { if (!r.ok)
            throw Error('构件库读取失败'); return r.json(); }).then(value => { if (live)
            setPresets(value.modules); }).catch(e => { if (live)
            setError(String(e)); });
        return () => { live = false; };
    }, []);
    if (!state)
        return null;
    const locked = disabled || pending;
    async function run(operation) {
        setPending(true);
        setError('');
        try {
            await onEdit(operation);
        }
        catch (e) {
            setError(String(e));
        }
        finally {
            setPending(false);
        }
    }
    async function compile(replaceModule) {
        setPending(true);
        setError('');
        // Pin this request to its starting workspace/selection. The App callback
        // also rejects a source response if the user loaded another model meanwhile.
        const id = node?.id, workspaceId = state.workspaceId, baseDocumentSha256 = snapshot?.nativeDocument?.documentSha256;
        try {
            const constructor = JSON.parse(moduleConfig);
            if (!constructor || typeof constructor !== 'object' || Array.isArray(constructor))
                throw Error('构造参数必须是 JSON 对象');
            const module = await onCompile({ source: moduleSource, entry: moduleEntry, constructor });
            await onEdit({ action: replaceModule ? 'replace-module' : 'add-source', ...(replaceModule ? { id } : {}), workspaceId, baseDocumentSha256, module });
        }
        catch (e) {
            setError(String(e));
        }
        finally {
            setPending(false);
        }
    }
    async function certify() {
        setPending(true);
        setError('');
        const workspaceId = state.workspaceId, baseDocumentSha256 = snapshot?.nativeDocument?.documentSha256;
        try {
            const generic = snapshot?.graph?.generic;
            if (!generic?.ir)
                throw Error('当前组装视图尚未就绪。');
            const ir = generic.ir;
            const result = await onCertify(ir);
            await onEdit({ action: 'certify', workspaceId, baseDocumentSha256, result });
        }
        catch (e) {
            setError(String(e));
        }
        finally {
            setPending(false);
        }
    }
    const match = (value) => value.toLowerCase().includes(query.toLowerCase());
    const ports = (direction) => {
        const found = new Map();
        for (const n of state.nodes.filter(n => n.parent === state.scope))
            for (const p of n.ports[direction]) {
                const value = JSON.stringify({ node: p.node, port: p.port });
                if (!found.has(value))
                    found.set(value, { value, label: `${n.label} · ${p.label} [${p.port}] · ${p.node}` });
            }
        return [...found.values()];
    };
    const outputs = ports('outputs'), inputs = ports('inputs');
    const validPorts = outputs.some(p => p.value === from) && inputs.some(p => p.value === to);
    return _jsxs("div", { className: "summary-authoring-panel", children: [_jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "Summary \u6A21\u578B\u7F16\u8F91" }), _jsx("p", { className: "field-help", children: "\u7F16\u8F91\u72EC\u7ACB\u7EC4\u88C5\u526F\u672C\u3002\u6E90\u7801\u4E0E\u539F\u59CB\u8BC1\u636E\u4FDD\u7559\u4E3A\u6765\u6E90\uFF1B\u65B0\u8FDE\u63A5\u3001\u53C2\u6570\u548C\u7EC4\u5408\u5C1A\u672A\u6267\u884C\u9A8C\u8BC1\u3002\u4FDD\u5B58\u5230\u6D4F\u89C8\u5668\uFF0C\u7F16\u8F91 JSON \u53EF\u642C\u8FD0\u3002" }), error && _jsx("p", { role: "alert", children: error }), _jsxs("label", { className: "field-label", children: ["\u6A21\u578B\u540D\u79F0", _jsx("input", { "aria-label": "Summary \u6A21\u578B\u540D\u79F0", value: modelTitle, onChange: e => setModelTitle(e.target.value) })] }), _jsx("button", { disabled: locked || !modelTitle.trim() || modelTitle === state.title, onClick: () => void run({ action: 'title', title: modelTitle }), children: "\u5E94\u7528\u6A21\u578B\u540D\u79F0" }), _jsxs("label", { className: "field-label", children: ["\u7F16\u8F91\u5C42\u7EA7", _jsxs("select", { "aria-label": "Summary \u7F16\u8F91\u5C42\u7EA7", value: state.scope ?? '', disabled: locked, onChange: e => void run({ action: 'scope', id: e.target.value || null }), children: [_jsx("option", { value: "", children: "\u6A21\u578B\u9876\u5C42" }), state.nodes.filter(n => n.kind === 'composite').map(n => _jsxs("option", { value: n.id, children: [n.label, " \u00B7 ", n.id] }, n.id))] })] }), _jsx("button", { disabled: locked || !state.scope, onClick: () => void run({ action: 'scope', id: state.nodes.find(n => n.id === state.scope)?.parent ?? null }), children: "\u8FD4\u56DE\u4E0A\u4E00\u7EA7" })] }), _jsxs("details", { className: "inspector-section", open: true, children: [_jsx("summary", { children: "\u539F\u5B50\u4E0E\u6A21\u5757\u5E93" }), _jsx("input", { "aria-label": "\u641C\u7D22 Summary \u6784\u4EF6", placeholder: "\u641C\u7D22\u6A21\u5757\u3001\u7B97\u5B50\u6216\u6E90\u7801\u6784\u4EF6\u2026", value: query, onChange: e => setQuery(e.target.value) }), _jsxs("div", { className: "segmented", children: [_jsx("button", { disabled: locked, onClick: () => void run({ action: 'interface', role: 'input', label: 'input' }), children: "\u6DFB\u52A0\u8F93\u5165" }), _jsx("button", { disabled: locked, onClick: () => void run({ action: 'interface', role: 'output', label: 'output' }), children: "\u6DFB\u52A0\u8F93\u51FA" })] }), _jsx("div", { className: "summary-authoring-library", children: presets.map((m, index) => ({ ...m, index })).filter(m => match(m.title)).map(m => _jsxs("button", { className: "full-button", disabled: locked, onClick: () => void run({ action: 'add', preset: m.index }), children: [m.title, m.level === 'atomic' ? ' · 原子' : ''] }, m.index)) }), _jsxs("details", { children: [_jsxs("summary", { children: ["\u6211\u7684\u7EC4\u5408\u6A21\u5757\uFF08", state.library.length, "\uFF09"] }), state.library.map((m, i) => _jsx("button", { className: "full-button", disabled: locked, onClick: () => void run({ action: 'add', library: i }), children: m.title }, i))] }), _jsxs("details", { children: [_jsxs("summary", { children: ["\u539F\u59CB\u6E90\u7801\u6784\u4EF6\uFF08", state.sourceNodes.length, "\uFF09"] }), _jsx("div", { className: "summary-authoring-library", children: state.sourceNodes.filter(n => match(n.label + ' ' + n.kind)).map(n => _jsxs("button", { className: "full-button", disabled: locked, onClick: () => void run({ action: 'add', sourceNode: n.id }), children: [n.label, " \u00B7 ", n.kind] }, n.id)) })] })] }), _jsxs("details", { className: "inspector-section", open: true, children: [_jsx("summary", { children: "\u8282\u70B9\u4E0E\u7ED3\u6784\u7F16\u8F91" }), _jsxs("p", { className: "field-help", children: ["\u5DF2\u9009 ", chosen.length, " \u4E2A\u539F\u59CB\u8282\u70B9\u3002\u5408\u5E76\u56FE\u5143\u8BF7\u5148\u5C55\u5F00\uFF0C\u518D\u7F16\u8F91\u5177\u4F53\u6784\u4EF6\u3002"] }), node && _jsxs(_Fragment, { children: [_jsxs("label", { className: "field-label", children: ["\u8282\u70B9\u540D\u79F0", _jsx("input", { "aria-label": "Summary \u8282\u70B9\u540D\u79F0", value: label, onChange: e => setLabel(e.target.value) })] }), _jsx("button", { disabled: locked || !label.trim(), onClick: () => void run({ action: 'edit', id: node.id, fields: { label } }), children: "\u5E94\u7528\u8282\u70B9\u540D\u79F0" }), _jsxs("details", { children: [_jsx("summary", { children: "\u53C2\u6570\u58F0\u660E" }), _jsx("textarea", { "aria-label": "Summary \u53C2\u6570\u58F0\u660E", rows: 6, value: fields, onChange: e => setFields(e.target.value) }), _jsx("button", { disabled: locked, onClick: () => { try {
                                            void run({ action: 'edit', id: node.id, fields: JSON.parse(fields) });
                                        }
                                        catch (e) {
                                            setError(String(e));
                                        } }, children: "\u5E94\u7528\u53C2\u6570\u58F0\u660E" }), _jsx("p", { className: "field-help", children: "\u58F0\u660E\u4E0D\u6539\u5199 Python\u3002\u66F4\u65B0\u6A21\u5757\u7684\u6E90\u7801\u4E8B\u5B9E\u8BF7\u4F7F\u7528\u201C\u6E90\u7801\u6A21\u5757\u4E0E\u53C2\u6570\u91CD\u89E3\u6790\u201D\u3002" })] })] }), _jsxs("div", { className: "segmented", children: [_jsx("button", { disabled: locked || !chosen.length, onClick: () => void run({ action: 'duplicate', ids: chosen.map(n => n.id) }), children: "\u590D\u5236\u9009\u4E2D\u6784\u4EF6" }), _jsx("button", { disabled: locked || !chosen.length, onClick: () => void run({ action: 'erase', ids: chosen.map(n => n.id) }), children: "\u5220\u9664\u9009\u4E2D\u6784\u4EF6" })] }), _jsxs("label", { className: "field-label", children: ["\u7EC4\u5408\u540D\u79F0", _jsx("input", { "aria-label": "Summary \u7EC4\u5408\u540D\u79F0", value: name, onChange: e => setName(e.target.value) })] }), _jsxs("div", { className: "segmented", children: [_jsx("button", { disabled: locked || !chosen.length, onClick: () => void run({ action: 'group', ids: chosen.map(n => n.id), title: name }), children: "\u7EC4\u5408\u4E3A\u6A21\u5757" }), _jsx("button", { disabled: locked || !chosen.length, onClick: () => void run({ action: 'library', ids: chosen.map(n => n.id), title: name }), children: "\u4FDD\u5B58\u7EC4\u5408\u5230\u5E93" })] })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u7CBE\u786E\u69FD\u4F4D\u8FDE\u63A5" }), _jsx("p", { className: "field-help", children: "\u5F53\u524D\u7F16\u8F91\u5C42\u7EA7\u7684\u771F\u5B9E producer / consumer \u69FD\u4F4D\u3002\u8F93\u5165\u5DF2\u6709\u9A71\u52A8\u65F6\u9700\u8981\u660E\u786E\u9009\u62E9\u66FF\u6362\u3002" }), _jsxs("label", { className: "field-label", children: ["\u8F93\u51FA\u69FD\u4F4D", _jsxs("select", { "aria-label": "Summary \u8F93\u51FA\u69FD\u4F4D", disabled: locked, value: outputs.some(p => p.value === from) ? from : '', onChange: e => setFrom(e.target.value), children: [_jsx("option", { value: "", children: "\u9009\u62E9\u8F93\u51FA" }), outputs.map(p => _jsx("option", { value: p.value, children: p.label }, p.value))] })] }), _jsxs("label", { className: "field-label", children: ["\u8F93\u5165\u69FD\u4F4D", _jsxs("select", { "aria-label": "Summary \u8F93\u5165\u69FD\u4F4D", disabled: locked, value: inputs.some(p => p.value === to) ? to : '', onChange: e => setTo(e.target.value), children: [_jsx("option", { value: "", children: "\u9009\u62E9\u8F93\u5165" }), inputs.map(p => _jsx("option", { value: p.value, children: p.label }, p.value))] })] }), _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: replace, onChange: e => setReplace(e.target.checked) }), "\u660E\u786E\u66FF\u6362\u8F93\u5165\u5DF2\u6709\u8FDE\u63A5"] }), _jsx("button", { disabled: locked || !validPorts, onClick: () => void run({ action: 'connect', source: JSON.parse(from), target: JSON.parse(to), replace }), children: "\u5EFA\u7ACB\u7CBE\u786E\u8FDE\u63A5" }), _jsxs("label", { className: "field-label", children: ["\u539F\u59CB\u4F9D\u8D56", _jsxs("select", { "aria-label": "Summary \u539F\u59CB\u4F9D\u8D56", value: state.edges.some(e => e.id === edgeId) ? edgeId : '', disabled: locked, onChange: e => setEdgeId(e.target.value), children: [_jsx("option", { value: "", children: "\u9009\u62E9\u4E00\u6761\u539F\u59CB\u4F9D\u8D56" }), state.edges.map(e => _jsxs("option", { value: e.id, children: [e.source, "[", e.source_port, "] \u2192 ", e.target, "[", e.target_port, "]"] }, e.id))] })] }), _jsxs("div", { className: "segmented", children: [_jsx("button", { disabled: locked || !state.edges.some(e => e.id === edgeId), onClick: () => void run({ action: 'remove-edge', id: edgeId }), children: "\u5220\u9664\u539F\u59CB\u4F9D\u8D56" }), _jsx("button", { disabled: locked || !validPorts || !state.edges.some(e => e.id === edgeId), onClick: () => void run({ action: 'rewire', id: edgeId, source: JSON.parse(from), target: JSON.parse(to), replace }), children: "\u91CD\u63A5\u539F\u59CB\u4F9D\u8D56" })] })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u6E90\u7801\u6A21\u5757\u4E0E\u53C2\u6570\u91CD\u89E3\u6790" }), _jsx("p", { className: "field-help", children: "\u4FDD\u7559\u6E90\u7801\u6587\u672C\u4E0E\u6784\u9020\u53C2\u6570\uFF0C\u9759\u6001\u63D0\u53D6 Summary \u6A21\u5757\u3002\u66FF\u6362\u9009\u4E2D\u6784\u4EF6\u65F6\u6309\u540C\u540D\u63A5\u53E3\u4FDD\u7559\u8FDE\u63A5\uFF1B\u79FB\u9664\u5DF2\u8FDE\u63A5\u63A5\u53E3\u4F1A\u62D2\u7EDD\uFF0C\u539F\u7A3F\u53EF\u7EE7\u7EED\u7F16\u8F91\u3002" }), _jsxs("label", { className: "field-label", children: ["\u6A21\u5757\u5165\u53E3", _jsx("input", { "aria-label": "Summary \u6A21\u5757\u5165\u53E3", value: moduleEntry, onChange: e => setModuleEntry(e.target.value) })] }), _jsxs("label", { className: "field-label", children: ["\u6784\u9020\u53C2\u6570", _jsx("textarea", { "aria-label": "Summary \u6A21\u5757\u6784\u9020\u53C2\u6570", rows: 4, value: moduleConfig, onChange: e => setModuleConfig(e.target.value) })] }), _jsxs("label", { className: "field-label", children: ["Python \u6E90\u7801", _jsx("textarea", { "aria-label": "Summary \u6A21\u5757\u6E90\u7801", rows: 10, spellCheck: false, value: moduleSource, onChange: e => setModuleSource(e.target.value) })] }), _jsxs("div", { className: "segmented", children: [_jsx("button", { disabled: locked || !moduleSource.trim() || !moduleEntry.trim(), onClick: () => void compile(false), children: "\u89E3\u6790\u5E76\u52A0\u5165\u6E90\u7801\u6A21\u5757" }), _jsx("button", { disabled: locked || !node, onClick: () => void compile(true), children: "\u91CD\u65B0\u89E3\u6790\u5E76\u66FF\u6362\u9009\u4E2D\u6784\u4EF6" })] }), _jsx("p", { className: "field-help", children: "\u6B64\u64CD\u4F5C\u53EA\u66F4\u65B0\u7EC4\u88C5\u7A3F\u3002Python \u4E0D\u6267\u884C\uFF0C\u4E5F\u4E0D\u5199\u56DE\u539F\u59CB\u6A21\u578B\u3002" })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u539F\u59CB\u6784\u4EF6\u7CBE\u786E\u91CD\u5EFA" }), _jsx("p", { className: "field-help", children: "\u4ECE\u539F\u59CB\u53C2\u8003 IR \u5206\u89E3\u4E3A\u6784\u4EF6\uFF0C\u518D\u9010\u4E2A\u6062\u590D\u539F\u8EAB\u4EFD\u548C\u8DE8\u6784\u4EF6\u69FD\u4F4D\u8FDE\u63A5\u3002\u5F00\u59CB\u540E\u5F53\u524D\u642D\u5EFA\u53EF\u64A4\u9500\uFF1B\u8FD9\u4E0D\u4F1A\u751F\u6210\u6216\u6267\u884C Python\u3002" }), _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: recipeAtomic, onChange: e => setRecipeAtomic(e.target.checked) }), "\u6309\u6E90\u7801\u539F\u5B50\u9010\u4E2A\u91CD\u5EFA"] }), _jsx("button", { disabled: locked || !state.sourceNodes.length, onClick: () => void run({ action: 'recipe-start', atomic: recipeAtomic }), children: "\u6E05\u7A7A\u642D\u5EFA\u5E76\u5F00\u59CB\u53C2\u8003\u91CD\u5EFA" }), state.recipe && _jsxs(_Fragment, { children: [_jsxs("p", { className: "field-help", children: [state.recipe.parts.length, " \u4E2A\u53C2\u8003\u6784\u4EF6 \u00B7 ", state.recipe.pendingConnections, " \u6761\u8DE8\u6784\u4EF6\u8FDE\u63A5\u5F85\u6062\u590D", state.recipe.exact ? ' · 原始节点与依赖已精确重建' : ''] }), _jsx("div", { className: "summary-authoring-library", children: state.recipe.parts.map(p => _jsxs("button", { className: "full-button", disabled: locked || p.present, onClick: () => void run({ action: 'recipe-add', part: p.index }), children: [p.present ? '已加入 · ' : '恢复构件 · ', p.title, "\uFF08", p.nodes, "\uFF09"] }, p.index)) }), _jsx("button", { disabled: locked || !state.recipe.readyConnections, onClick: () => void run({ action: 'recipe-wires' }), children: "\u6062\u590D\u73B0\u6709\u7AEF\u70B9\u7684\u7CBE\u786E\u8FDE\u63A5" })] })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u7EC4\u88C5\u5C40\u90E8\u7ED3\u6784\u590D\u6838" }), _jsx("p", { className: "field-help", children: "\u68C0\u67E5\u5F53\u524D\u7EC4\u88C5\u7A3F\u7684\u64CD\u4F5C\u6570\u5173\u7CFB\uFF0C\u91CD\u65B0\u8BC6\u522B\u53EF\u7528\u7684\u5C40\u90E8\u8BED\u4E49\u5951\u7EA6\u3002\u7ED3\u679C\u53EA\u8986\u76D6\u58F0\u660E\u7ED3\u6784\uFF1B\u4E0D\u8868\u793A Python \u7B49\u4EF7\u3001shape \u517C\u5BB9\u6216\u6A21\u578B\u6267\u884C\u901A\u8FC7\u3002" }), _jsx("button", { disabled: locked || !state.edited, onClick: () => void certify(), children: "\u590D\u6838\u5F53\u524D\u7EC4\u88C5\u7ED3\u6784" }), state.localAnalysis ? _jsxs("p", { className: "field-help", role: "status", children: ["\u5DF2\u4FDD\u5B58\u5C40\u90E8\u7ED3\u6784\u7ED3\u679C\uFF1A", state.localAnalysis.contracts, " \u9879\u5951\u7EA6\uFF1B\u6587\u6863\u6765\u6E90\uFF0C\u6A21\u578B\u672A\u6267\u884C\u3002\u7ED3\u6784\u7F16\u8F91\u540E\u9700\u91CD\u65B0\u590D\u6838\u3002"] }) : _jsx("p", { className: "field-help", children: state.edited ? '当前组装稿尚无局部结构复核结果。' : '当前为原始参考事实；结构编辑后可复核组装稿。' })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u6B63\u5F0F\u6E90\u7801\u7F16\u8F91" }), _jsx("p", { className: "field-help", children: "\u7EC4\u88C5\u58F0\u660E\u4E0D\u6388\u4E88\u6E90\u7801\u4E8B\u52A1\u6743\u9650\u3002Python \u5DE5\u4F5C\u526F\u672C\u4ECD\u4F7F\u7528\u53D7\u7BA1\u7406\u7684\u89E3\u6790\u3001\u5BA1\u67E5\u548C\u63D0\u4EA4\u6D41\u7A0B\u3002" }), _jsx("button", { disabled: locked, onClick: onFormal, children: "\u6253\u5F00\u6B63\u5F0F\u6E90\u7801\u5DE5\u4F5C\u526F\u672C" })] })] });
}
