import { useEffect, useState } from 'react';
import { loadSummaryCatalog, summaryCatalogBlockReason, summaryPrograms, summaryConfiguration, type SummaryCatalogModel } from './summaryCatalog';

/** Source programs are library entries; constructor variants remain explicit. */
export function SummaryCatalogPanel({ disabled, onOpen, onBrowseSaved, open: expanded, onToggle }: {
  disabled: boolean; onOpen: (model: SummaryCatalogModel) => Promise<void>;
  onBrowseSaved: () => void; open: boolean; onToggle: (open: boolean) => void;
}) {
  const [models, setModels] = useState<SummaryCatalogModel[]>([]), [query, setQuery] = useState('');
  const [selected, setSelected] = useState(''), [variant, setVariant] = useState('');
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    void loadSummaryCatalog(abort.signal).then(catalog => {
      if (abort.signal.aborted) return;
      setModels(catalog.models); setLoaded(true);
    }).catch(e => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, []);
  const programs = summaryPrograms(models);
  const filtered = programs.filter(program => `${program.title} ${program.models.map(m => m.id).join(' ')}`.toLowerCase().includes(query.trim().toLowerCase()));
  const chosen = filtered.find(program => program.id === selected) ?? filtered[0];
  const model = chosen?.models.find(model => model.id === variant) ?? chosen?.models.find(model => !summaryCatalogBlockReason(model)) ?? chosen?.models[0];
  const reason = model && summaryCatalogBlockReason(model);
  async function open() {
    if (!model || disabled || pending || reason) return;
    setPending(true); setError('');
    try { await onOpen(model); } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  return <details className="inspector-section summary-catalog" open={expanded} onToggle={event => onToggle(event.currentTarget.open)}>
    <summary>模型库<span className="read-only">{loaded ? `${programs.length} 个模型` : '读取目录'}</span></summary>
    {error && <p className="field-help" role="alert">{error}</p>}
    {loaded && <>
      <label className="field">搜索模型<input aria-label="搜索 Summary 模型" value={query} onChange={e => setQuery(e.target.value)} placeholder="模型名称" /></label>
      <label className="field">模型<select aria-label="Summary 目录模型" value={chosen?.id ?? ''} onChange={e => { setSelected(e.target.value); setVariant(''); }} disabled={disabled || pending || !chosen}>
        {!chosen && <option value="">没有匹配的模型</option>}
        {filtered.map(program => <option key={program.id} value={program.id}>{program.title}</option>)}
      </select></label>
      {chosen && chosen.models.length > 1 && <details className="summary-model-configurations"><summary>模型配置 · {chosen.models.length}</summary>
        <label className="field-label">构造参数<select aria-label="Summary 模型配置" disabled={disabled || pending} value={model?.id ?? ''} onChange={e => setVariant(e.target.value)}>{chosen.models.map(model => <option key={model.id} value={model.id}>{summaryConfiguration(model)}</option>)}</select></label>
        <p className="field-help">同一源码入口的不同实例。观察记录只适用于对应的构造参数与输入，打开配置会载入该实例。</p>
      </details>}
      {model && <p className="field-help">{model.nodes} 个原始节点 · {model.edges} 条依赖{model.program?.observations ? ` · ${model.program.observations} 条观察记录` : ''}</p>}
      {reason && <p className="field-help">{reason}</p>}
      <button className="full-button" disabled={disabled || pending || !model || !!reason} onClick={() => void open()}>{pending ? '正在打开…' : '打开模型'}</button>
      <button className="text-button" disabled={disabled || pending} onClick={onBrowseSaved}>已保存与导入文档</button>
    </>}
  </details>;
}
