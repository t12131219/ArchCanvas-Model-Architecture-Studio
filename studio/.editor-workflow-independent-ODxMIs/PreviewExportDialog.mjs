import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useRef, useState } from 'react';
import { detailExportChoices } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/index.ts';
import { api } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/api.ts';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-ODxMIs/icons.mjs';
import { PreviewPublicationRequestGate, previewPublicationCacheKey, readPreviewPublicationCache, sanitizePreviewPublication, writePreviewPublicationCache } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewPublication.ts';
export function PreviewExportDialog({ document, selectedId, capabilities, onClose, previewExport }) {
    const [dpi, setDpi] = useState(300), [scope, setScope] = useState('document');
    const [detailNodeId, setDetailNodeId] = useState(selectedId ?? ''), [widthInput, setWidthInput] = useState(String(document.pageSpec.widthMm));
    const [format, setFormat] = useState(capabilities?.publicationExport.pdf ? 'pdf' : 'svg');
    const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState('');
    const [publication, setPublication] = useState(null), [artifact, setArtifact] = useState(null);
    const [documentDownloaded, setDocumentDownloaded] = useState(false);
    const documentFormat = format === 'json' || format === 'source';
    const gate = useRef(new PreviewPublicationRequestGate()), renderSource = useRef(previewExport.svg);
    renderSource.current = previewExport.svg;
    const width = Number(widthInput), widthValid = widthInput.trim() !== '' && Number.isFinite(width) && width >= 25 && width <= 1000;
    const choices = useMemo(() => previewExport.detailChoices ?? detailExportChoices(document).map(choice => ({ nodeId: choice.nodeId, pathLabel: choice.pathLabel })), [document, previewExport.detailChoices]);
    const detailAvailable = choices.length > 0, effectiveDetailId = choices.find(choice => choice.nodeId === detailNodeId)?.nodeId ?? choices[0]?.nodeId;
    const effectiveScope = scope === 'detail' && detailAvailable ? 'detail' : 'document';
    const sourceBinding = JSON.stringify(previewExport.binding), storageKey = `archcanvas.preview-export.v1:${previewExport.binding.caseId}`;
    const physical = publication?.physical, heightValid = !!physical && physical.heightMm <= 5000;
    const available = capabilities?.publicationExport;
    const cacheKey = publication && widthValid ? previewPublicationCacheKey(publication.svg, previewExport.binding, { scope: effectiveScope, nodeId: effectiveScope === 'detail' ? effectiveDetailId : undefined, widthMm: width, format, dpi }) : null;
    useEffect(() => {
        const ticket = gate.current.begin();
        setPublication(null);
        setArtifact(null);
        setError('');
        setBusy(false);
        if (!widthValid) {
            setLoading(false);
            return;
        }
        setLoading(true);
        const source = renderSource.current;
        void source(effectiveScope === 'detail' ? effectiveDetailId : undefined).then(svg => {
            const result = sanitizePreviewPublication(svg, width);
            if (gate.current.isCurrent(ticket)) {
                setPublication(result);
                setLoading(false);
            }
        }).catch(reason => { if (gate.current.isCurrent(ticket)) {
            setError(String(reason));
            setLoading(false);
        } });
        return () => gate.current.invalidate();
    }, [sourceBinding, effectiveScope, effectiveDetailId, width, widthValid]);
    useEffect(() => {
        if (!cacheKey)
            return;
        try {
            setArtifact(readPreviewPublicationCache(localStorage.getItem(storageKey), cacheKey));
        }
        catch {
            setArtifact(null);
        }
    }, [cacheKey, storageKey]);
    async function generate() {
        const json = format === 'source' ? previewExport.sourcePackage : previewExport.editingDocument;
        if (documentFormat && json) {
            const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
            const link = window.document.createElement('a');
            link.href = url;
            link.download = `${document.title}-${format === 'source' ? 'source-adapter' : 'canvas'}.json`;
            window.document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1500);
            setDocumentDownloaded(true);
            return;
        }
        if (!publication || !cacheKey || !widthValid || !heightValid)
            return;
        const ticket = gate.current.begin(), svg = publication.svg, key = cacheKey;
        setBusy(true);
        setError('');
        setArtifact(null);
        try {
            const result = await api.previewExport(svg, format, dpi, width, previewExport.binding);
            if (!gate.current.isCurrent(ticket))
                return;
            setArtifact(result);
            try {
                localStorage.setItem(storageKey, writePreviewPublicationCache(result, key));
            }
            catch { /* The file remains available. */ }
        }
        catch (reason) {
            if (gate.current.isCurrent(ticket))
                setError(String(reason));
        }
        finally {
            if (gate.current.isCurrent(ticket))
                setBusy(false);
        }
    }
    return _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { className: "export-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "export-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "PUBLICATION EXPORT" }), _jsx("h2", { id: "export-title", children: "\u5BFC\u51FA\u5F53\u524D\u753B\u5E03" })] }), _jsx("button", { className: "tool", disabled: busy, onClick: onClose, "aria-label": "\u5173\u95ED\u5BFC\u51FA", children: _jsx(Icon, { name: "close" }) })] }), _jsxs("p", { children: [document.title, " \u00B7 \u89C6\u89C9\u7248\u672C ", previewExport.binding.revision ?? document.revision, " \u00B7 ", document.pageSpec.preset === 'paper' ? '彩色' : '黑白'] }), !documentFormat && _jsxs(_Fragment, { children: [_jsxs("label", { className: "field-label", children: ["\u5BFC\u51FA\u8303\u56F4", _jsxs("select", { className: "field-select", "aria-label": "\u5BFC\u51FA\u8303\u56F4", value: effectiveScope, disabled: busy, onChange: event => { setScope(event.target.value); setArtifact(null); }, children: [_jsx("option", { value: "document", children: "\u6574\u4E2A\u5F53\u524D\u753B\u5E03" }), _jsx("option", { value: "detail", disabled: !detailAvailable, children: "\u5DF2\u5C55\u5F00\u5BB9\u5668\u7684\u8BE6\u60C5\u9875" })] })] }), effectiveScope === 'detail' && _jsxs("label", { className: "field-label", children: ["\u8BE6\u60C5\u5BB9\u5668", _jsx("select", { className: "field-select", "aria-label": "\u8BE6\u60C5\u5BB9\u5668", value: effectiveDetailId, disabled: busy, onChange: event => { setDetailNodeId(event.target.value); setArtifact(null); }, children: choices.map((choice, index) => _jsxs("option", { value: choice.nodeId, children: [index + 1, ". ", choice.pathLabel] }, choice.nodeId)) })] }), !detailAvailable && _jsx("p", { className: "field-help", children: "\u5C55\u5F00\u4E00\u4E2A\u53EF\u89C1\u5BB9\u5668\u540E\uFF0C\u53EF\u751F\u6210\u4FDD\u7559\u5F53\u524D\u5185\u90E8\u6392\u7248\u7684\u72EC\u7ACB\u8BE6\u60C5\u9875\u3002" }), _jsxs("label", { className: "field-label", children: ["\u51FA\u7248\u5BBD\u5EA6", _jsxs("select", { className: "field-select", "aria-label": "\u5BFC\u51FA\u5BBD\u5EA6", disabled: busy, value: widthValid ? width : '', onChange: event => { setWidthInput(event.target.value); setArtifact(null); }, children: [!widthValid && _jsx("option", { value: "", children: "\u586B\u5199\u81EA\u5B9A\u4E49\u5BBD\u5EA6" }), [...new Set([85, 180, document.pageSpec.widthMm, ...(widthValid ? [width] : [])])].sort((a, b) => a - b).map(value => _jsxs("option", { value: value, children: [value, " mm"] }, value))] })] }), _jsxs("label", { className: "field-label", children: ["\u81EA\u5B9A\u4E49\u5BBD\u5EA6\uFF0825\u20131000 mm\uFF09", _jsx("input", { className: "field-select", type: "number", min: 25, max: 1000, step: "any", "aria-label": "\u81EA\u5B9A\u4E49\u5BFC\u51FA\u5BBD\u5EA6", disabled: busy, value: widthInput, onChange: event => { setWidthInput(event.target.value); setArtifact(null); } })] }), !widthValid && _jsx("p", { className: "error-text", role: "alert", children: "\u8BF7\u8F93\u5165 25\u20131000 mm \u4E4B\u95F4\u7684\u9875\u5BBD\u3002" }), widthValid && physical && _jsxs("div", { className: "export-preflight", children: [_jsx("b", { children: "\u6700\u7EC8\u5C3A\u5BF8\u6587\u5B57\u9884\u68C0" }), _jsxs("p", { children: ["\u9875\u9762 ", width, " \u00D7 ", physical.heightMm.toFixed(1), " mm"] }), _jsxs("p", { children: ["\u8282\u70B9\u540D\u79F0 ", physical.nodeLabelPt.toFixed(2), " pt \u00B7 \u6700\u5C0F\u6587\u5B57 ", physical.minTextPt.toFixed(2), " pt \u00B7 \u4E3B\u7EBF ", physical.minMainLinePt.toFixed(2), " pt"] }), physical.minTextPt < 7 && _jsxs(_Fragment, { children: [_jsxs("p", { children: ["\u4EE5 7 pt \u4E3A\u8D77\u70B9\uFF0C\u6B64\u8303\u56F4\u9700\u8981\u81F3\u5C11 ", physical.suggestedWidthFor7Pt, " \u00D7 ", physical.suggestedHeightFor7Pt.toFixed(1), " mm\u3002\u53EF\u589E\u5927\u9875\u5BBD\u6216\u663E\u5F0F\u9009\u62E9\u66F4\u5C0F\u7684\u8BE6\u60C5\u8303\u56F4\uFF1B\u8BF7\u540C\u65F6\u6838\u5BF9\u9875\u9AD8\u4E0E\u76EE\u6807\u7248\u9762\u3002"] }), physical.suggestedWidthFor7Pt <= 1000 && physical.suggestedHeightFor7Pt <= 5000 ? _jsxs("button", { disabled: busy, onClick: () => { setWidthInput(String(physical.suggestedWidthFor7Pt)); setArtifact(null); }, children: ["\u91C7\u7528\u5EFA\u8BAE\u9875\u5BBD ", physical.suggestedWidthFor7Pt, " mm"] }) : _jsx("p", { className: "field-help", children: "\u5EFA\u8BAE\u5C3A\u5BF8\u8D85\u51FA\u5F53\u524D\u5BFC\u51FA\u652F\u6301\u7684 1000 mm \u5BBD\u6216 5000 mm \u9AD8\u3002\u8BF7\u8C03\u6574\u6392\u7248\u6216\u663E\u5F0F\u9009\u62E9\u66F4\u5C0F\u7684\u8BE6\u60C5\u8303\u56F4\u3002" })] }), _jsx("p", { className: "field-help", children: "\u5B57\u53F7\u6309\u771F\u5B9E\u9884\u89C8\u7684\u5BFC\u51FA\u5C3A\u5BF8\u8BA1\u7B97\uFF0C7 pt \u662F\u8D77\u59CB\u5EFA\u8BAE\u3002\u5B57\u4F53\u3001\u8FDE\u7EBF\u4E0E\u5B9E\u9645\u9605\u8BFB\u6548\u679C\u4ECD\u9700\u5BA1\u770B\u3002" })] }), physical && !heightValid && _jsx("p", { className: "error-text", role: "alert", children: "\u5F53\u524D\u9875\u9AD8\u8D85\u8FC7 5000 mm \u5BFC\u51FA\u4E0A\u9650\uFF0C\u8BF7\u51CF\u5C0F\u9875\u5BBD\u6216\u8C03\u6574\u8303\u56F4\u3002" }), loading && _jsx("p", { className: "field-help", role: "status", children: "\u6B63\u5728\u8BFB\u53D6\u5F53\u524D\u9884\u89C8\u7684\u771F\u5B9E SVG\u2026" }), publication && widthValid && _jsx("div", { "aria-label": effectiveScope === 'detail' ? '详情页预览' : '整图预览', style: { maxHeight: 240, overflow: 'auto', border: '1px solid #dbe2ea', background: '#fff' }, dangerouslySetInnerHTML: { __html: publication.svg } })] }), _jsxs("div", { className: "export-formats", children: [['svg', 'pdf', 'png'].map(value => _jsxs("button", { disabled: busy || !available?.[value], className: format === value ? 'active' : '', onClick: () => { setFormat(value); setArtifact(null); setDocumentDownloaded(false); }, children: [value.toUpperCase(), _jsx("small", { children: value === 'png' ? '高分辨率位图' : '矢量输出' })] }, value)), previewExport.editingDocument && _jsxs("button", { disabled: busy, className: format === 'json' ? 'active' : '', onClick: () => { setFormat('json'); setArtifact(null); setDocumentDownloaded(false); }, children: ["\u7F16\u8F91 JSON", _jsx("small", { children: "\u5B8C\u6574\u753B\u5E03\u6587\u6863" })] }), previewExport.sourcePackage && _jsxs("button", { disabled: busy, className: format === 'source' ? 'active' : '', onClick: () => { setFormat('source'); setArtifact(null); setDocumentDownloaded(false); }, children: ["\u6E90\u7801\u5305", _jsx("small", { children: "\u6E90\u7801\u3001IR \u4E0E\u8BC1\u636E" })] })] }), format === 'json' && _jsxs(_Fragment, { children: [_jsx("p", { children: "\u4FDD\u5B58\u5B8C\u6574\u753B\u5E03\u7684\u9012\u5F52\u5C55\u5F00\u3001\u5E03\u5C40\u3001\u8FDE\u63A5\u8349\u7A3F\u3001\u5E03\u7EBF\u4E0E\u6837\u5F0F\uFF1B\u5BFC\u5165\u7684\u6A21\u578B\u540C\u65F6\u4FDD\u7559\u6E90\u7801\u9002\u914D\u5305\u3002\u901A\u8FC7\u201C\u5BFC\u5165 Python \u6E90\u7801\u201D\u4E2D\u7684 JSON \u5165\u53E3\u53EF\u6062\u590D\u7F16\u8F91\u3002" }), documentDownloaded && _jsx("p", { role: "status", children: "\u7F16\u8F91 JSON \u5DF2\u4E0B\u8F7D\u3002" })] }), format === 'source' && _jsxs(_Fragment, { children: [_jsx("p", { children: "\u4E0B\u8F7D\u5BFC\u5165\u6A21\u578B\u7684\u539F\u59CB\u6E90\u7801\u3001\u7EDF\u4E00 IR \u4E0E\u6765\u6E90\u8BC1\u636E\uFF0C\u4E0D\u5305\u542B\u540E\u7EED\u89C6\u89C9\u7F16\u8F91\u3002\u901A\u8FC7\u5BFC\u5165\u5165\u53E3\u53EF\u91CD\u65B0\u6253\u5F00\u6A21\u578B\u3002" }), documentDownloaded && _jsx("p", { role: "status", children: "\u6E90\u7801\u5305\u5DF2\u4E0B\u8F7D\u3002" })] }), format === 'png' && _jsxs("label", { className: "field-label", children: ["PNG \u5206\u8FA8\u7387", _jsx("select", { className: "field-select", "aria-label": "\u5BFC\u51FA DPI", value: dpi, disabled: busy, onChange: event => { setDpi(Number(event.target.value)); setArtifact(null); }, children: [150, 300, 600].map(value => _jsxs("option", { value: value, children: [value, " DPI"] }, value)) })] }), !documentFormat && _jsx("p", { className: "field-help", children: "\u9884\u89C8\u548C\u4E0B\u8F7D\u4F7F\u7528\u540C\u4E00\u4EFD\u771F\u5B9E SVG\uFF0C\u4FDD\u7559\u5F53\u524D\u51E0\u4F55\u3001\u663E\u793A\u540D\u4E0E\u6837\u5F0F\u3002PDF \u5B57\u4F53\u7531\u672C\u673A\u89E3\u6790\uFF1B\u8BF7\u5728\u76EE\u6807\u9605\u8BFB\u5668\u68C0\u67E5\u5B57\u4F53\u3002" }), !documentFormat && !available?.[format] && _jsxs("p", { className: "error-text", children: ["\u6B64\u683C\u5F0F\u5728\u5F53\u524D\u670D\u52A1\u73AF\u5883\u4E0D\u53EF\u7528\u3002", available?.unavailableReason] }), error && !documentFormat && _jsx("p", { className: "error-text", role: "alert", children: error }), artifact && _jsxs("div", { className: "export-result", children: [_jsxs("b", { children: ["\u6587\u4EF6\u5DF2\u751F\u6210 \u00B7 ", artifact.format.toUpperCase()] }), _jsxs("div", { children: [_jsxs("a", { href: artifact.url, target: "_blank", rel: "noreferrer", children: ["\u67E5\u770B ", artifact.format.toUpperCase()] }), _jsx("a", { href: artifact.url, download: `${document.title}.${artifact.format}`, children: "\u4E0B\u8F7D\u6587\u4EF6" }), _jsx("a", { href: artifact.receiptUrl, target: "_blank", rel: "noreferrer", children: "\u67E5\u770B\u5BFC\u51FA\u6536\u636E" })] }), _jsxs("details", { children: [_jsx("summary", { children: "\u5C3A\u5BF8\u3001\u6458\u8981\u4E0E\u5B57\u4F53\u4FE1\u606F" }), _jsx("pre", { children: JSON.stringify(artifact.receipt, null, 2) })] })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { disabled: busy, onClick: onClose, children: "\u5173\u95ED" }), _jsx("button", { className: "primary", disabled: documentFormat ? !(format === 'source' ? previewExport.sourcePackage : previewExport.editingDocument) : busy || loading || !publication || !widthValid || !heightValid || !available?.[format], onClick: () => void generate(), children: format === 'json' ? '下载编辑 JSON' : format === 'source' ? '下载源码包' : busy ? '正在生成…' : '生成文件' })] })] }) });
}
