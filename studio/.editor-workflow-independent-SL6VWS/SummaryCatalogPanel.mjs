import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { loadSummaryCatalog, summaryCatalogBlockReason } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/summaryCatalog.ts';
/** Studio folding section; opening uses Summary's existing import authority. */
export function SummaryCatalogPanel({ disabled, onOpen, open: expanded, onToggle }) {
    const [models, setModels] = useState([]), [query, setQuery] = useState(''), [selected, setSelected] = useState('');
    const [pending, setPending] = useState(false), [error, setError] = useState(''), [loaded, setLoaded] = useState(false);
    useEffect(() => {
        const abort = new AbortController();
        void loadSummaryCatalog(abort.signal).then(catalog => {
            if (abort.signal.aborted)
                return;
            setModels(catalog.models);
            setSelected(catalog.models.find(m => !summaryCatalogBlockReason(m))?.id ?? '');
            setLoaded(true);
        }).catch(e => { if (!abort.signal.aborted)
            setError(String(e)); });
        return () => abort.abort();
    }, []);
    const filtered = models.filter(m => `${m.title} ${m.id}`.toLowerCase().includes(query.trim().toLowerCase()));
    const chosen = filtered.find(m => m.id === selected) ?? filtered.find(m => !summaryCatalogBlockReason(m));
    const available = models.filter(m => !summaryCatalogBlockReason(m)), blocked = models.filter(m => summaryCatalogBlockReason(m));
    async function open() {
        if (!chosen || disabled || pending)
            return;
        setPending(true);
        setError('');
        try {
            await onOpen(chosen);
        }
        catch (e) {
            setError(String(e));
        }
        finally {
            setPending(false);
        }
    }
    return _jsxs("details", { className: "inspector-section summary-catalog", open: expanded, onToggle: event => onToggle(event.currentTarget.open), children: [_jsxs("summary", { children: ["Summary \u6A21\u578B\u5E93", _jsx("span", { className: "read-only", children: loaded ? `${models.length} 个模型` : '读取目录' })] }), error && _jsx("p", { className: "field-help", role: "alert", children: error }), loaded && _jsxs(_Fragment, { children: [_jsxs("label", { className: "field", children: ["\u641C\u7D22\u6A21\u578B", _jsx("input", { "aria-label": "\u641C\u7D22 Summary \u6A21\u578B", value: query, onChange: e => setQuery(e.target.value), placeholder: "\u540D\u79F0\u6216\u6A21\u578B\u8EAB\u4EFD" })] }), _jsxs("label", { className: "field", children: ["\u6A21\u578B", _jsxs("select", { "aria-label": "Summary \u76EE\u5F55\u6A21\u578B", value: chosen?.id ?? '', onChange: e => setSelected(e.target.value), disabled: disabled || pending || !chosen, children: [!chosen && _jsx("option", { value: "", children: "\u6CA1\u6709\u9884\u7B97\u5185\u7684\u5339\u914D\u6A21\u578B" }), filtered.map(model => _jsxs("option", { value: model.id, disabled: !!summaryCatalogBlockReason(model), children: [model.title, summaryCatalogBlockReason(model) ? ' · 超出当前预算' : ''] }, model.id))] })] }), chosen && _jsxs(_Fragment, { children: [_jsxs("div", { className: "coordinate-row", children: [_jsxs("label", { children: ["\u539F\u59CB\u8282\u70B9 ", _jsx("output", { children: chosen.nodes })] }), _jsxs("label", { children: ["\u7CBE\u786E\u4F9D\u8D56 ", _jsx("output", { children: chosen.edges })] })] }), _jsxs("p", { className: "field-help", children: [chosen.runtime === 'passed' ? '含归档运行证据；本次未执行模型。' : '原始静态语义；本次未执行模型。', " \u8986\u76D6\u8BB0\u5F55\uFF1A", chosen.coverage ?? '未提供', "\u3002"] })] }), _jsx("button", { className: "full-button", disabled: disabled || pending || !chosen, onClick: () => void open(), children: pending ? '正在打开…' : '打开 Summary 模型' }), _jsxs("p", { className: "field-help", children: [available.length, " \u4E2A\u53EF\u6253\u5F00\uFF0C", blocked.length, " \u4E2A\u8D85\u51FA\u5F53\u524D\u9884\u7B97\u3002\u5C55\u5F00\u3001\u89D2\u8272\u3001\u7F16\u8F91\u526F\u672C\u548C\u4FDD\u5B58\u6CBF\u7528 Summary\uFF1B\u5F52\u6863\u6765\u6E90\u8DEF\u5F84\u53EA\u4F5C\u8BC1\u636E\u3002"] }), !!blocked.length && _jsxs("details", { children: [_jsxs("summary", { children: ["\u5927\u56FE\u9884\u7B97\u4E0E\u4FDD\u7559\u6570\u636E \u00B7 ", blocked.length] }), blocked.map(model => _jsxs("p", { className: "field-help", children: [_jsx("b", { children: model.title }), _jsx("br", {}), summaryCatalogBlockReason(model), " \u5B8C\u6574 IR \u5DF2\u4FDD\u7559\uFF0C\u5F85\u5927\u56FE\u4FDD\u5B58\u3001\u4F20\u8F93\u548C\u5386\u53F2\u5185\u5B58\u9A8C\u8BC1\u540E\u5F00\u653E\u3002"] }, model.id))] })] })] });
}
