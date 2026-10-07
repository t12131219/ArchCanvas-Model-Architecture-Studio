import { useMemo, useState } from 'react';
import { buildExportScene, detailExportChoices, publicationPreflight, renderSvg } from './core';
import type { CanvasDocument } from './core';
import { api } from './api';
import type { Capabilities, ExportArtifact } from './api';
import { Icon } from './icons';
import { readExportCache, writeExportCache } from './exportCache';

export function ExportDialog({ document, selectedId, capabilities, onClose }: { document: CanvasDocument; selectedId?: string; capabilities: Capabilities | null; onClose: () => void }) {
  const storageKey = `archcanvas.export.v2:${document.id}`;
  const [dpi, setDpi] = useState(300);
  const [scope, setScope] = useState<'document' | 'detail'>('document');
  const [detailNodeId, setDetailNodeId] = useState(selectedId ?? '');
  const [widthInput, setWidthInput] = useState(String(document.pageSpec.widthMm));
  const parsedWidth = Number(widthInput);
  const widthValid = widthInput.trim() !== '' && Number.isFinite(parsedWidth) && parsedWidth >= 25 && parsedWidth <= 1000;
  const widthMm = widthValid ? parsedWidth : document.pageSpec.widthMm;
  const [artifact, setArtifact] = useState<ExportArtifact | null>(() => {
    try { return readExportCache(localStorage.getItem(storageKey), document, renderSvg(buildExportScene(document))); }
    catch { return null; }
  });
  const [format, setFormat] = useState(artifact?.format ?? (capabilities?.publicationExport.pdf ? 'pdf' : 'svg'));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function generate() {
    if (!widthValid || !heightValid) return;
    setBusy(true); setError(''); setArtifact(null);
    try {
      const artifact = await api.export(document, format, dpi, { widthMm, ...(effectiveScope === 'detail' ? { nodeId: effectiveDetailId } : {}) });
      setArtifact(artifact);
      try { localStorage.setItem(storageKey, writeExportCache(artifact, svg)); } catch { /* The generated file remains available if browser storage is full. */ }
    }
    catch (error) { setError(String(error)); }
    finally { setBusy(false); }
  }
  const available = capabilities?.publicationExport;
  const choices = useMemo(() => detailExportChoices(document), [document]);
  const detailAvailable = choices.length > 0;
  const effectiveDetailId = choices.find(choice => choice.nodeId === detailNodeId)?.nodeId ?? choices[0]?.nodeId;
  const effectiveScope = scope === 'detail' && detailAvailable ? 'detail' : 'document';
  const scene = useMemo(() => buildExportScene(document, { widthMm, ...(effectiveScope === 'detail' ? { nodeId: effectiveDetailId } : {}) }), [document, effectiveScope, effectiveDetailId, widthMm]);
  const svg = useMemo(() => renderSvg(scene), [scene]);
  const physical = useMemo(() => publicationPreflight(scene), [scene]);
  const heightValid = physical.heightMm <= 5000;
  return <div className="modal-backdrop"><div className="export-modal" role="dialog" aria-modal="true" aria-labelledby="export-title"><div className="modal-heading"><div><div className="eyebrow">PUBLICATION EXPORT</div><h2 id="export-title">导出当前画布</h2></div><button className="tool" disabled={busy} onClick={onClose} aria-label="关闭导出"><Icon name="close" /></button></div>
    <p>{document.title} · 视觉版本 {document.revision} · {document.pageSpec.preset === 'paper' ? '彩色' : '黑白'}</p>
    <label className="field-label">导出范围<select className="field-select" aria-label="导出范围" value={effectiveScope} disabled={busy} onChange={e => { setScope(e.target.value as 'document' | 'detail'); setArtifact(null); }}><option value="document">整个当前画布</option><option value="detail" disabled={!detailAvailable}>已展开容器的详情页</option></select></label>
    {effectiveScope === 'detail' && <label className="field-label">详情容器<select className="field-select" aria-label="详情容器" disabled={busy} value={effectiveDetailId} onChange={e => { setDetailNodeId(e.target.value); setArtifact(null); }}>{choices.map((choice, index) => <option key={choice.nodeId} value={choice.nodeId}>{index + 1}. {choice.pathLabel} · 最小 {(choice.minTextPt * widthMm / choice.widthMm).toFixed(2)} pt · {(choice.heightMm * widthMm / choice.widthMm).toFixed(0)} mm 高</option>)}</select></label>}
    {!detailAvailable && <p className="field-help">展开一个可见容器后，可生成保留当前内部排版与跨边界连接的独立详情页。</p>}
    <label className="field-label">出版宽度<select className="field-select" aria-label="导出宽度" value={widthValid ? widthMm : ''} disabled={busy} onChange={e => { setWidthInput(e.target.value); setArtifact(null); }}>{!widthValid && <option value="">填写自定义宽度</option>}{[...new Set([85, 180, document.pageSpec.widthMm, ...(widthValid ? [widthMm] : [])])].sort((a, b) => a - b).map(width => <option key={width} value={width}>{width} mm</option>)}</select></label>
    <label className="field-label">自定义宽度（25–1000 mm）<input className="field-select" type="number" min={25} max={1000} step="any" aria-label="自定义导出宽度" disabled={busy} value={widthInput} onChange={e => { setWidthInput(e.target.value); setArtifact(null); }} /></label>
    {!widthValid && <p className="error-text" role="alert">请输入 25–1000 mm 之间的页宽。</p>}
    {widthValid && <div className="export-preflight"><b>最终尺寸文字预检</b><p>页面 {widthMm} × {physical.heightMm.toFixed(1)} mm</p><p>节点名称 {physical.nodeLabelPt.toFixed(2)} pt · 最小文字 {physical.minTextPt.toFixed(2)} pt · 主线 {physical.minMainLinePt.toFixed(2)} pt</p>{physical.minTextPt < 7 && <><p>以 7 pt 为起点，此范围需要至少 {physical.suggestedWidthFor7Pt} × {physical.suggestedHeightFor7Pt.toFixed(1)} mm。可增大页宽或显式选择更小的详情范围；请同时核对页高与目标版面。</p>{physical.suggestedWidthFor7Pt <= 1000 && physical.suggestedHeightFor7Pt <= 5000 ? <button disabled={busy} onClick={() => { setWidthInput(String(physical.suggestedWidthFor7Pt)); setArtifact(null); }}>采用建议页宽 {physical.suggestedWidthFor7Pt} mm</button> : <p className="field-help">建议尺寸超出当前导出支持的 1000 mm 宽或 5000 mm 高。请调整排版或显式选择更小的详情范围。</p>}</>}<p className="field-help">字号按导出尺寸计算，7 pt 是起始建议。字体、连线与实际阅读效果仍需审看。</p></div>}
    {widthValid && !heightValid && <p className="error-text" role="alert">当前页高超过 5000 mm 导出上限，请减小页宽或调整范围。</p>}
    {scene.exportScope && <><p className="field-help">详情页显示 {scene.exportScope.boundaryEdges.length} 条跨边界绑定；外部来源/消费者以 FROM / TO 标明。当前内部折叠关系、无关边与区域外说明保留于收据清单。</p><details><summary>详情范围与边界清单</summary><pre>{JSON.stringify(scene.exportScope, null, 2)}</pre></details></>}
    {widthValid && <div aria-label={scene.exportScope ? '详情页预览' : '整图预览'} style={{ maxHeight: 240, overflow: 'auto', border: '1px solid #dbe2ea', background: '#fff' }} dangerouslySetInnerHTML={{ __html: svg }} />}
    <div className="export-formats">{(['svg', 'pdf', 'png'] as const).map(f => <button disabled={busy || !available?.[f]} className={format === f ? 'active' : ''} key={f} onClick={() => { setFormat(f); setArtifact(null); }}>{f.toUpperCase()}<small>{f === 'png' ? '高分辨率位图' : '矢量输出'}</small></button>)}</div>
    {format === 'png' && <label className="field-label">PNG 分辨率<select className="field-select" aria-label="导出 DPI" value={dpi} disabled={busy} onChange={e => { setDpi(Number(e.target.value)); setArtifact(null); }}>{[150, 300, 600].map(d => <option key={d} value={d}>{d} DPI</option>)}</select></label>}
    <p className="field-help">导出使用打开此面板时的画布版本，保留显示名、样式、图例与说明。PDF 字体由本机解析；请在目标阅读器检查字体。</p>
    {!available?.[format as 'svg'] && <p className="error-text">此格式在当前服务环境不可用。{available?.unavailableReason}</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {artifact && <div className="export-result"><b>文件已生成 · {artifact.format.toUpperCase()}</b><div><a href={artifact.url} target="_blank" rel="noreferrer">查看 {artifact.format.toUpperCase()}</a><a href={artifact.url} download={`${document.title}.${artifact.format}`}>下载文件</a><a href={artifact.receiptUrl} target="_blank" rel="noreferrer">查看导出收据</a></div><details><summary>尺寸、摘要与字体信息</summary><pre>{JSON.stringify(artifact.receipt, null, 2)}</pre></details></div>}
    <div className="modal-actions"><button disabled={busy} onClick={onClose}>关闭</button><button className="primary" disabled={busy || !widthValid || !heightValid || !available?.[format as 'svg']} onClick={() => void generate()}>{busy ? '正在生成…' : '生成文件'}</button></div>
  </div></div>;
}
