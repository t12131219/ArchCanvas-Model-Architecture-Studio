import { useEffect, useMemo, useRef, useState } from 'react';
import { detailExportChoices } from './core/index.ts';
import type { CanvasDocument } from './core/types.ts';
import { api } from './api.ts';
import type { Capabilities, ExportArtifact } from './api.ts';
import { Icon } from './icons.tsx';
import { PreviewPublicationRequestGate, previewPublicationCacheKey, readPreviewPublicationCache, sanitizePreviewPublication, writePreviewPublicationCache } from './previewPublication.ts';
import type { PreviewExportSource, PreviewPublication } from './previewPublication.ts';

export function PreviewExportDialog({ document, selectedId, capabilities, onClose, previewExport }: {
  document: CanvasDocument; selectedId?: string; capabilities: Capabilities | null; onClose: () => void; previewExport: PreviewExportSource;
}) {
  const [dpi, setDpi] = useState(300), [scope, setScope] = useState<'document' | 'detail'>('document');
  const [detailNodeId, setDetailNodeId] = useState(selectedId ?? ''), [widthInput, setWidthInput] = useState(String(document.pageSpec.widthMm));
  const [format, setFormat] = useState(capabilities?.publicationExport.pdf ? 'pdf' : 'svg');
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState('');
  const [publication, setPublication] = useState<PreviewPublication | null>(null), [artifact, setArtifact] = useState<ExportArtifact | null>(null);
  const gate = useRef(new PreviewPublicationRequestGate()), renderSource = useRef(previewExport.svg);
  renderSource.current = previewExport.svg;
  const width = Number(widthInput), widthValid = widthInput.trim() !== '' && Number.isFinite(width) && width >= 25 && width <= 1000;
  const choices = useMemo(() => previewExport.detailChoices ?? detailExportChoices(document).map(choice => ({ nodeId: choice.nodeId, pathLabel: choice.pathLabel })), [document, previewExport.detailChoices]);
  const detailAvailable = choices.length > 0, effectiveDetailId = choices.find(choice => choice.nodeId === detailNodeId)?.nodeId ?? choices[0]?.nodeId;
  const effectiveScope = scope === 'detail' && detailAvailable ? 'detail' : 'document';
  const sourceBinding = JSON.stringify(previewExport.binding), storageKey = `archcanvas.preview-export.v1:${previewExport.binding.caseId}`;
  const physical = publication?.physical, heightValid = !!physical && physical.heightMm <= 5000;
  const available = capabilities?.publicationExport;
  const cacheKey = publication && widthValid ? previewPublicationCacheKey(publication.svg, previewExport.binding,
    { scope: effectiveScope, nodeId: effectiveScope === 'detail' ? effectiveDetailId : undefined, widthMm: width, format, dpi }) : null;

  useEffect(() => {
    const ticket = gate.current.begin();
    setPublication(null); setArtifact(null); setError(''); setBusy(false);
    if (!widthValid) { setLoading(false); return; }
    setLoading(true);
    const source = renderSource.current;
    void source(effectiveScope === 'detail' ? effectiveDetailId : undefined).then(svg => {
      const result = sanitizePreviewPublication(svg, width);
      if (gate.current.isCurrent(ticket)) { setPublication(result); setLoading(false); }
    }).catch(reason => { if (gate.current.isCurrent(ticket)) { setError(String(reason)); setLoading(false); } });
    return () => gate.current.invalidate();
  }, [sourceBinding, effectiveScope, effectiveDetailId, width, widthValid]);

  useEffect(() => {
    if (!cacheKey) return;
    try { setArtifact(readPreviewPublicationCache(localStorage.getItem(storageKey), cacheKey)); } catch { setArtifact(null); }
  }, [cacheKey, storageKey]);

  async function generate() {
    if (!publication || !cacheKey || !widthValid || !heightValid) return;
    const ticket = gate.current.begin(), svg = publication.svg, key = cacheKey;
    setBusy(true); setError(''); setArtifact(null);
    try {
      const result = await api.previewExport(svg, format, dpi, width, previewExport.binding);
      if (!gate.current.isCurrent(ticket)) return;
      setArtifact(result);
      try { localStorage.setItem(storageKey, writePreviewPublicationCache(result, key)); } catch { /* The file remains available. */ }
    } catch (reason) { if (gate.current.isCurrent(ticket)) setError(String(reason)); }
    finally { if (gate.current.isCurrent(ticket)) setBusy(false); }
  }

  return <div className="modal-backdrop"><div className="export-modal" role="dialog" aria-modal="true" aria-labelledby="export-title"><div className="modal-heading"><div><div className="eyebrow">PUBLICATION EXPORT</div><h2 id="export-title">导出当前画布</h2></div><button className="tool" disabled={busy} onClick={onClose} aria-label="关闭导出"><Icon name="close" /></button></div>
    <p>{document.title} · 视觉版本 {previewExport.binding.revision ?? document.revision} · {document.pageSpec.preset === 'paper' ? '彩色' : '黑白'}</p>
    <label className="field-label">导出范围<select className="field-select" aria-label="导出范围" value={effectiveScope} disabled={busy} onChange={event => { setScope(event.target.value as 'document' | 'detail'); setArtifact(null); }}><option value="document">整个当前画布</option><option value="detail" disabled={!detailAvailable}>已展开容器的详情页</option></select></label>
    {effectiveScope === 'detail' && <label className="field-label">详情容器<select className="field-select" aria-label="详情容器" value={effectiveDetailId} disabled={busy} onChange={event => { setDetailNodeId(event.target.value); setArtifact(null); }}>{choices.map((choice, index) => <option key={choice.nodeId} value={choice.nodeId}>{index + 1}. {choice.pathLabel}</option>)}</select></label>}
    {!detailAvailable && <p className="field-help">展开一个可见容器后，可生成保留当前内部排版的独立详情页。</p>}
    <label className="field-label">出版宽度<select className="field-select" aria-label="导出宽度" disabled={busy} value={widthValid ? width : ''} onChange={event => { setWidthInput(event.target.value); setArtifact(null); }}>{!widthValid && <option value="">填写自定义宽度</option>}{[...new Set([85, 180, document.pageSpec.widthMm, ...(widthValid ? [width] : [])])].sort((a, b) => a - b).map(value => <option key={value} value={value}>{value} mm</option>)}</select></label>
    <label className="field-label">自定义宽度（25–1000 mm）<input className="field-select" type="number" min={25} max={1000} step="any" aria-label="自定义导出宽度" disabled={busy} value={widthInput} onChange={event => { setWidthInput(event.target.value); setArtifact(null); }} /></label>
    {!widthValid && <p className="error-text" role="alert">请输入 25–1000 mm 之间的页宽。</p>}
    {widthValid && physical && <div className="export-preflight"><b>最终尺寸文字预检</b><p>页面 {width} × {physical.heightMm.toFixed(1)} mm</p><p>节点名称 {physical.nodeLabelPt.toFixed(2)} pt · 最小文字 {physical.minTextPt.toFixed(2)} pt · 主线 {physical.minMainLinePt.toFixed(2)} pt</p>{physical.minTextPt < 7 && <><p>以 7 pt 为起点，此范围需要至少 {physical.suggestedWidthFor7Pt} × {physical.suggestedHeightFor7Pt.toFixed(1)} mm。可增大页宽或显式选择更小的详情范围；请同时核对页高与目标版面。</p>{physical.suggestedWidthFor7Pt <= 1000 && physical.suggestedHeightFor7Pt <= 5000 ? <button disabled={busy} onClick={() => { setWidthInput(String(physical.suggestedWidthFor7Pt)); setArtifact(null); }}>采用建议页宽 {physical.suggestedWidthFor7Pt} mm</button> : <p className="field-help">建议尺寸超出当前导出支持的 1000 mm 宽或 5000 mm 高。请调整排版或显式选择更小的详情范围。</p>}</>}<p className="field-help">字号按真实预览的导出尺寸计算，7 pt 是起始建议。字体、连线与实际阅读效果仍需审看。</p></div>}
    {physical && !heightValid && <p className="error-text" role="alert">当前页高超过 5000 mm 导出上限，请减小页宽或调整范围。</p>}
    {loading && <p className="field-help" role="status">正在读取当前预览的真实 SVG…</p>}
    {publication && widthValid && <div aria-label={effectiveScope === 'detail' ? '详情页预览' : '整图预览'} style={{ maxHeight: 240, overflow: 'auto', border: '1px solid #dbe2ea', background: '#fff' }} dangerouslySetInnerHTML={{ __html: publication.svg }} />}
    <div className="export-formats">{(['svg', 'pdf', 'png'] as const).map(value => <button disabled={busy || !available?.[value]} className={format === value ? 'active' : ''} key={value} onClick={() => { setFormat(value); setArtifact(null); }}>{value.toUpperCase()}<small>{value === 'png' ? '高分辨率位图' : '矢量输出'}</small></button>)}</div>
    {format === 'png' && <label className="field-label">PNG 分辨率<select className="field-select" aria-label="导出 DPI" value={dpi} disabled={busy} onChange={event => { setDpi(Number(event.target.value)); setArtifact(null); }}>{[150, 300, 600].map(value => <option key={value} value={value}>{value} DPI</option>)}</select></label>}
    <p className="field-help">预览和下载使用同一份真实 SVG，保留当前几何、显示名与样式。PDF 字体由本机解析；请在目标阅读器检查字体。</p>
    {!available?.[format as 'svg'] && <p className="error-text">此格式在当前服务环境不可用。{available?.unavailableReason}</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {artifact && <div className="export-result"><b>文件已生成 · {artifact.format.toUpperCase()}</b><div><a href={artifact.url} target="_blank" rel="noreferrer">查看 {artifact.format.toUpperCase()}</a><a href={artifact.url} download={`${document.title}.${artifact.format}`}>下载文件</a><a href={artifact.receiptUrl} target="_blank" rel="noreferrer">查看导出收据</a></div><details><summary>尺寸、摘要与字体信息</summary><pre>{JSON.stringify(artifact.receipt, null, 2)}</pre></details></div>}
    <div className="modal-actions"><button disabled={busy} onClick={onClose}>关闭</button><button className="primary" disabled={busy || loading || !publication || !widthValid || !heightValid || !available?.[format as 'svg']} onClick={() => void generate()}>{busy ? '正在生成…' : '生成文件'}</button></div>
  </div></div>;
}
