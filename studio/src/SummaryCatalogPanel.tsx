import { useEffect, useState } from 'react';
import { loadSummaryCatalog, loadSummaryPreviewCases, summaryCatalogBlockReason, type SummaryCatalogModel, type SummaryPreviewCase } from './summaryCatalog';

/** Studio folding section; opening uses Summary's existing import authority. */
export function SummaryCatalogPanel({ disabled, onOpen, onOpenPreview, onBrowseSaved, open: expanded, onToggle }: {
  disabled: boolean; onOpen: (model: SummaryCatalogModel) => Promise<void>;
  onOpenPreview: (id: string) => Promise<void>;
  onBrowseSaved: () => void;
  open: boolean; onToggle: (open: boolean) => void;
}) {
  const [models,setModels] = useState<SummaryCatalogModel[]>([]), [query,setQuery] = useState(''), [selected,setSelected] = useState('');
  const [previews, setPreviews] = useState<SummaryPreviewCase[]>([]);
  const [pending,setPending] = useState(false), [error,setError] = useState(''), [loaded,setLoaded] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    void Promise.all([loadSummaryCatalog(abort.signal), loadSummaryPreviewCases(abort.signal)]).then(([catalog, cases]) => {
      if (abort.signal.aborted) return;
      setModels(catalog.models); setPreviews(cases); setSelected(catalog.models.find(m => !summaryCatalogBlockReason(m))?.id ?? ''); setLoaded(true);
    }).catch(e => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, []);
  const filtered = models.filter(m => `${m.title} ${m.id}`.toLowerCase().includes(query.trim().toLowerCase()));
  const filteredPreviews = previews.filter(m => `${m.title} ${m.id}`.toLowerCase().includes(query.trim().toLowerCase()));
  const chosen = filtered.find(m => m.id === selected) ?? filtered.find(m => !summaryCatalogBlockReason(m));
  const available = models.filter(m => !summaryCatalogBlockReason(m)), blocked = models.filter(m => summaryCatalogBlockReason(m));
  async function open() {
    if (!chosen || disabled || pending) return;
    setPending(true); setError('');
    try { await onOpen(chosen); } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  async function openPreview(id: string) {
    if (disabled || pending) return;
    setPending(true); setError('');
    try { await onOpenPreview(id); } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  return <details className="inspector-section summary-catalog" open={expanded} onToggle={event => onToggle(event.currentTarget.open)}>
    <summary>Summary 模型库<span className="read-only">{loaded ? `${models.length + previews.length} 个案例` : '读取目录'}</span></summary>
    {error && <p className="field-help" role="alert">{error}</p>}
    {loaded && <>
      <label className="field">搜索模型<input aria-label="搜索 Summary 模型" value={query} onChange={e => setQuery(e.target.value)} placeholder="名称或模型身份" /></label>
      <h3 className="summary-library-heading">预览案例 · {previews.length}</h3>
      <div className="summary-preview-cases">{filteredPreviews.map(item => <button className="full-button" key={item.id} disabled={disabled || pending} onClick={() => void openPreview(item.id)}>{item.title}</button>)}</div>
      {!filteredPreviews.length && <p className="field-help">没有匹配的预览案例。</p>}
      <h3 className="summary-library-heading">语义模型 · {models.length}</h3>
      <label className="field">模型<select aria-label="Summary 目录模型" value={chosen?.id ?? ''} onChange={e => setSelected(e.target.value)} disabled={disabled || pending || !chosen}>
        {!chosen && <option value="">没有预算内的匹配模型</option>}
        {filtered.map(model => <option key={model.id} value={model.id} disabled={!!summaryCatalogBlockReason(model)}>{model.title}{summaryCatalogBlockReason(model) ? ' · 超出当前预算' : ''}</option>)}
      </select></label>
      {chosen && <><div className="coordinate-row"><label>原始节点 <output>{chosen.nodes}</output></label><label>精确依赖 <output>{chosen.edges}</output></label></div>
        <p className="field-help">{chosen.runtime === 'passed' ? '含归档运行证据；本次未执行模型。' : '原始静态语义；本次未执行模型。'} 覆盖记录：{chosen.coverage ?? '未提供'}。</p></>}
      <button className="full-button" disabled={disabled || pending || !chosen} onClick={() => void open()}>{pending ? '正在打开…' : '打开 Summary 模型'}</button>
      <p className="field-help">{available.length} 个语义模型可打开，{blocked.length} 个超出当前预算。预览案例与语义模型均来自当前 Summary_Merge。展开、角色、编辑副本和保存沿用 Summary。</p>
      <button className="full-button" disabled={disabled || pending} onClick={onBrowseSaved}>浏览已保存与导入模型</button>
      {!!blocked.length && <details><summary>大图预算与保留数据 · {blocked.length}</summary>{blocked.map(model => <p className="field-help" key={model.id}><b>{model.title}</b><br />{summaryCatalogBlockReason(model)} 完整 IR 已保留，待大图保存、传输和历史内存验证后开放。</p>)}</details>}
    </>}
  </details>;
}
