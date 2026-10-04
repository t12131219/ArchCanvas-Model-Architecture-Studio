import { useState } from 'react';
import type { CanvasDocument } from './core';
import { api } from './api';
import type { Capabilities, ExportArtifact } from './api';
import { Icon } from './icons';

export function ExportDialog({ document, capabilities, onClose }: { document: CanvasDocument; capabilities: Capabilities | null; onClose: () => void }) {
  const storageKey = `archcanvas.export.v1:${document.id}`;
  const [dpi, setDpi] = useState(300);
  const [artifact, setArtifact] = useState<ExportArtifact | null>(() => {
    try { const stored = JSON.parse(localStorage.getItem(storageKey) ?? 'null') as ExportArtifact | null; return stored?.receipt.revision === document.revision ? stored : null; }
    catch { return null; }
  });
  const [format, setFormat] = useState(artifact?.format ?? (capabilities?.publicationExport.pdf ? 'pdf' : 'svg'));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function generate() {
    setBusy(true); setError(''); setArtifact(null);
    try { const artifact = await api.export(document, format, dpi); setArtifact(artifact); localStorage.setItem(storageKey, JSON.stringify(artifact)); }
    catch (error) { setError(String(error)); }
    finally { setBusy(false); }
  }
  const available = capabilities?.publicationExport;
  return <div className="modal-backdrop"><div className="export-modal" role="dialog" aria-modal="true" aria-labelledby="export-title"><div className="modal-heading"><div><div className="eyebrow">PUBLICATION EXPORT</div><h2 id="export-title">导出当前画布</h2></div><button className="tool" disabled={busy} onClick={onClose} aria-label="关闭导出"><Icon name="close" /></button></div>
    <p>{document.title} · 视觉版本 {document.revision} · {document.pageSpec.widthMm} mm · {document.pageSpec.preset === 'paper' ? '彩色' : '黑白'}</p>
    <div className="export-formats">{(['svg', 'pdf', 'png'] as const).map(f => <button disabled={busy || !available?.[f]} className={format === f ? 'active' : ''} key={f} onClick={() => { setFormat(f); setArtifact(null); }}>{f.toUpperCase()}<small>{f === 'png' ? '高分辨率位图' : '矢量输出'}</small></button>)}</div>
    {format === 'png' && <label className="field-label">PNG 分辨率<select className="field-select" aria-label="导出 DPI" value={dpi} disabled={busy} onChange={e => { setDpi(Number(e.target.value)); setArtifact(null); }}>{[150, 300, 600].map(d => <option key={d} value={d}>{d} DPI</option>)}</select></label>}
    <p className="field-help">导出使用打开此面板时的画布版本，保留显示名、样式、图例与说明。PDF 字体由本机解析；请在目标阅读器检查字体。</p>
    {!available?.[format as 'svg'] && <p className="error-text">此格式在当前服务环境不可用。{available?.unavailableReason}</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {artifact && <div className="export-result"><b>文件已生成 · {artifact.format.toUpperCase()}</b><div><a href={artifact.url} target="_blank" rel="noreferrer">查看 {artifact.format.toUpperCase()}</a><a href={artifact.url} download={`${document.title}.${artifact.format}`}>下载文件</a><a href={artifact.receiptUrl} target="_blank" rel="noreferrer">查看导出收据</a></div><details><summary>尺寸、摘要与字体信息</summary><pre>{JSON.stringify(artifact.receipt, null, 2)}</pre></details></div>}
    <div className="modal-actions"><button disabled={busy} onClick={onClose}>关闭</button><button className="primary" disabled={busy || !available?.[format as 'svg']} onClick={() => void generate()}>{busy ? '正在生成…' : '生成文件'}</button></div>
  </div></div>;
}
