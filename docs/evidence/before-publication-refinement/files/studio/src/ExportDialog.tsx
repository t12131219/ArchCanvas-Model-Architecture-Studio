import { useMemo, useState } from 'react';
import { buildExportScene, publicationPreflight, renderSvg } from './core';
import type { CanvasDocument } from './core';
import { api } from './api';
import type { Capabilities, ExportArtifact } from './api';
import { Icon } from './icons';

export function ExportDialog({ document, selectedId, capabilities, onClose }: { document: CanvasDocument; selectedId?: string; capabilities: Capabilities | null; onClose: () => void }) {
  const storageKey = `archcanvas.export.v1:${document.id}`;
  const [dpi, setDpi] = useState(300);
  const [scope, setScope] = useState<'document' | 'detail'>('document');
  const [widthMm, setWidthMm] = useState(document.pageSpec.widthMm);
  const [artifact, setArtifact] = useState<ExportArtifact | null>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) ?? 'null') as ExportArtifact | null;
      const savedScope = stored?.receipt.exportScope as { kind?: string } | undefined;
      return stored?.receipt.documentId === document.id && stored.receipt.revision === document.revision &&
        stored.receipt.sourceDigest === document.architecture.sourceDigest && stored.receipt.irDigest === document.architecture.irDigest &&
        stored.receipt.widthMm === document.pageSpec.widthMm && (!savedScope || savedScope.kind === 'document') ? stored : null;
    }
    catch { return null; }
  });
  const [format, setFormat] = useState(artifact?.format ?? (capabilities?.publicationExport.pdf ? 'pdf' : 'svg'));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function generate() {
    setBusy(true); setError(''); setArtifact(null);
    try { const artifact = await api.export(document, format, dpi, { widthMm, ...(effectiveScope === 'detail' ? { nodeId: selectedId } : {}) }); setArtifact(artifact); localStorage.setItem(storageKey, JSON.stringify(artifact)); }
    catch (error) { setError(String(error)); }
    finally { setBusy(false); }
  }
  const available = capabilities?.publicationExport;
  const fullScene = useMemo(() => buildExportScene(document), [document]);
  const detailAvailable = Boolean(fullScene.nodes.some(node => node.id === selectedId && node.expanded && node.expandable));
  const effectiveScope = scope === 'detail' && detailAvailable ? 'detail' : 'document';
  const scene = useMemo(() => buildExportScene(document, { widthMm, ...(effectiveScope === 'detail' ? { nodeId: selectedId } : {}) }), [document, effectiveScope, selectedId, widthMm]);
  const svg = useMemo(() => renderSvg(scene), [scene]);
  const physical = useMemo(() => publicationPreflight(scene), [scene]);
  return <div className="modal-backdrop"><div className="export-modal" role="dialog" aria-modal="true" aria-labelledby="export-title"><div className="modal-heading"><div><div className="eyebrow">PUBLICATION EXPORT</div><h2 id="export-title">导出当前画布</h2></div><button className="tool" disabled={busy} onClick={onClose} aria-label="关闭导出"><Icon name="close" /></button></div>
    <p>{document.title} · 视觉版本 {document.revision} · {widthMm} mm · {document.pageSpec.preset === 'paper' ? '彩色' : '黑白'}</p>
    <label className="field-label">导出范围<select className="field-select" aria-label="导出范围" value={effectiveScope} disabled={busy} onChange={e => { setScope(e.target.value as 'document' | 'detail'); setArtifact(null); }}><option value="document">整个当前画布</option><option value="detail" disabled={!detailAvailable}>选中已展开容器的详情页</option></select></label>
    {!detailAvailable && <p className="field-help">选中并展开一个可见容器后，可生成保留当前内部排版与跨边界连接的独立详情页。</p>}
    <label className="field-label">出版宽度<select className="field-select" aria-label="导出宽度" value={widthMm} disabled={busy} onChange={e => { setWidthMm(Number(e.target.value)); setArtifact(null); }}>{[...new Set([85, 180, document.pageSpec.widthMm])].sort((a, b) => a - b).map(width => <option key={width} value={width}>{width} mm</option>)}</select></label>
    <div className="export-preflight"><b>最终尺寸文字预检</b><p>节点名称 {physical.nodeLabelPt.toFixed(1)} pt · 最小文字 {physical.minTextPt.toFixed(1)} pt · 主线 {physical.minMainLinePt.toFixed(2)} pt</p>{physical.minTextPt < 7 && <p>当前细节在此宽度下较小。若以 7 pt 为目标，可将页面宽度设为至少 {physical.suggestedWidthFor7Pt} mm，或选择更小的详情容器。期刊要求请按实际版面选择。</p>}</div>
    {scene.exportScope && <><p className="field-help">详情页显示 {scene.exportScope.boundaryEdges.length} 条跨边界绑定；外部来源/消费者以 FROM / TO 标明。当前内部折叠关系、无关边与区域外说明保留于收据清单，未改模型或画布。</p><div aria-label="详情页预览" style={{ maxHeight: 240, overflow: 'auto', border: '1px solid #dbe2ea', background: '#fff' }} dangerouslySetInnerHTML={{ __html: svg }} /><details><summary>详情范围与边界清单</summary><pre>{JSON.stringify(scene.exportScope, null, 2)}</pre></details></>}
    <div className="export-formats">{(['svg', 'pdf', 'png'] as const).map(f => <button disabled={busy || !available?.[f]} className={format === f ? 'active' : ''} key={f} onClick={() => { setFormat(f); setArtifact(null); }}>{f.toUpperCase()}<small>{f === 'png' ? '高分辨率位图' : '矢量输出'}</small></button>)}</div>
    {format === 'png' && <label className="field-label">PNG 分辨率<select className="field-select" aria-label="导出 DPI" value={dpi} disabled={busy} onChange={e => { setDpi(Number(e.target.value)); setArtifact(null); }}>{[150, 300, 600].map(d => <option key={d} value={d}>{d} DPI</option>)}</select></label>}
    <p className="field-help">导出使用打开此面板时的画布版本，保留显示名、样式、图例与说明。PDF 字体由本机解析；请在目标阅读器检查字体。</p>
    {!available?.[format as 'svg'] && <p className="error-text">此格式在当前服务环境不可用。{available?.unavailableReason}</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {artifact && <div className="export-result"><b>文件已生成 · {artifact.format.toUpperCase()}</b><div><a href={artifact.url} target="_blank" rel="noreferrer">查看 {artifact.format.toUpperCase()}</a><a href={artifact.url} download={`${document.title}.${artifact.format}`}>下载文件</a><a href={artifact.receiptUrl} target="_blank" rel="noreferrer">查看导出收据</a></div><details><summary>尺寸、摘要与字体信息</summary><pre>{JSON.stringify(artifact.receipt, null, 2)}</pre></details></div>}
    <div className="modal-actions"><button disabled={busy} onClick={onClose}>关闭</button><button className="primary" disabled={busy || !available?.[format as 'svg']} onClick={() => void generate()}>{busy ? '正在生成…' : '生成文件'}</button></div>
  </div></div>;
}
