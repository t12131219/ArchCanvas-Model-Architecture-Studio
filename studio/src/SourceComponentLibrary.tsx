import { t, uiMessage } from './i18n';
import { useEffect, useState } from 'react';
import { SourceComponentImport } from './SourceComponentImport';

type Variant = { id: string; structure: string; nodes: number; edges: number; occurrences: number; sources: string[]; configuration: { component: string; constructor: unknown }[] };
type Family = { scope?: 'project'; id: string; title: string; aliases: string[]; category: string; variants: Variant[] };
type Catalog = { schema: string; stats: { candidates: number; families: number; variants: number }; families: Family[] };

function variantLabel(v: Variant, index: number) {
  const first = v.configuration[0]?.constructor as { args?: unknown[]; kwargs?: Record<string, unknown> } | undefined;
  const config = first ? [...(first.args ?? []), ...Object.entries(first.kwargs ?? first).filter(([k]) => !['args', 'kwargs'].includes(k)).map(([k, value]) => `${k}=${JSON.stringify(value)}`)].map(v => typeof v === 'string' ? v : JSON.stringify(v)).join(', ') : '';
  return t("版本 {0} · {1} 节点{2}", {0: index + 1, 1: v.nodes, 2: config ? ` · ${config.slice(0, 90)}` : ` · ${v.sources[0]}`});
}

function ComponentEntry({ family, disabled, onAdd }: { family: Family; disabled: boolean; onAdd: (id: string, scope?: 'project') => void }) {
  const [id, setId] = useState(family.variants[0].id);
  const variant = family.variants.find(v => v.id === id) ?? family.variants[0];
  const structures = new Set(family.variants.map(v => v.structure)).size;
  return <details className="source-component-entry">
    <summary><span>{family.title}</span><small>{family.scope ? t("项目库 · ") : ''}{family.variants.length}{t("个版本")}</small></summary>
    <div className="source-component-content">
      {family.variants.length > 1 && <label className="field-label">{t("结构与参数版本")}<select aria-label={t("{0} 构件版本", {"0": family.title})} value={variant.id} disabled={disabled} onChange={e => setId(e.target.value)}>{family.variants.map((v, index) => <option key={v.id} value={v.id}>{variantLabel(v, index)}</option>)}</select></label>}
      <p className="field-help">{variant.nodes}{t("节点 ·")}{variant.edges}{t("依赖")}{structures > 1 ? t(" · {0} 种结构", {"0": structures}) : ''}</p>
      <button className="full-button" disabled={disabled} onClick={() => onAdd(variant.id, family.scope)}>{t("加入")} {family.title}</button>
      <details className="source-component-provenance"><summary>{t("参数与来源")}</summary>
        {family.aliases.length > 0 && <p>{t("别名：")}{family.aliases.join('、')}</p>}
        <p>{t("归并")}{variant.occurrences}{t("个源码实例；来源：")}{variant.sources.join('、')}</p>
        {variant.configuration.length > 0 ? <pre>{JSON.stringify(variant.configuration, null, 2)}</pre> : <p>{t("此版本没有已解析的构造参数。")}</p>}
      </details>
    </div>
  </details>;
}

/** Mounted only when opened; no open-model or preset-document dependency. */
export function SourceComponentLibrary({ query, disabled, onAdd }: { query: string; disabled: boolean; onAdd: (id: string, scope?: 'project') => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null), [error, setError] = useState('');
  const [category, setCategory] = useState('模块'), [limit, setLimit] = useState(20), [retry, setRetry] = useState(0);
  const [projectCatalog, setProjectCatalog] = useState<Catalog | null>(null), [projectError, setProjectError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setError(''); setProjectError('');
    void fetch('/api/preview/source-components', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw Error('项目构件库暂不可用，请确认本地服务已更新并启动。');
      const value = await response.json() as Catalog;
      if (value.schema !== 'archcanvas-source-components/1' || !Array.isArray(value.families)) throw Error('项目构件库格式无效');
      if (!controller.signal.aborted) setProjectCatalog(value);
    }).catch(e => { if (!controller.signal.aborted) setProjectError(String(e)); });
    void fetch('/preview/data/source-components/index.json', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw Error('源码构件库读取失败');
      const value = await response.json() as Catalog;
      if (value.schema !== 'archcanvas-source-components/1' || !Array.isArray(value.families)) throw Error('源码构件库格式无效');
      if (!controller.signal.aborted) setCatalog(value);
    }).catch(e => { if (!controller.signal.aborted) setError(String(e)); });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => setLimit(20), [query, category]);
  if (error) return <div><p role="alert">{uiMessage(error)}</p><button onClick={() => setRetry(v => v + 1)}>{t("重新读取构件库")}</button></div>;
  if (!catalog) return <p className="field-help" role="status">{t("正在读取独立构件库…")}</p>;
  const term = query.trim().toLowerCase();
  const nameMatches = (f: Family) => [f.title, ...f.aliases].some(name => name.toLowerCase().includes(term));
  const allFamilies = [...(projectCatalog?.families ?? []).map(f => ({ ...f, scope: 'project' as const })), ...catalog.families];
  const families = allFamilies.filter(f => (!category || f.category === category) && (!term || [f.title, ...f.aliases, ...f.variants.flatMap(v => v.sources), JSON.stringify(f.variants.map(v => v.configuration))].join(' ').toLowerCase().includes(term))).sort((a, b) => Number(nameMatches(b)) - Number(nameMatches(a)));
  return <div className="source-component-library">
    <SourceComponentImport disabled={disabled} onSaved={() => setRetry(v => v + 1)} />
    {projectError && <p role="alert">{projectError}</p>}
    <p className="field-help">{allFamilies.length}{t("类构件 ·")}{catalog.stats.variants + (projectCatalog?.stats.variants ?? 0)}{t("个版本。可用于任意模型；参数与结构差异单独保留。")}</p>
    <div className="segmented" role="group" aria-label={t("源码构件类别")}>{[["模块", t("模块")], ["算子", t("算子")], ['', t("全部")]].map(([value, title]) => <button key={title} aria-pressed={category === value} onClick={() => setCategory(value)}>{title}</button>)}</div>
    <p className="field-help" role="status">{t("找到")} {families.length}{t("类构件")}</p>
    {families.slice(0, limit).map(family => <ComponentEntry key={`${family.scope ?? 'builtin'}:${family.id}`} family={family} disabled={disabled} onAdd={onAdd} />)}
    {!families.length && <p className="field-help">{t("没有匹配项，可切换类别或修改搜索词。")}</p>}
    {families.length > limit && <button className="full-button" onClick={() => setLimit(v => v + 20)}>{t("显示更多（还有")}{families.length - limit}{t("类）")}</button>}
  </div>;
}
