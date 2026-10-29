import { t, uiMessage } from './i18n';
import { lazy, Suspense, useEffect, useState } from 'react';
import { api } from './api';
const SourceCodeWindow = lazy(() => import('./SourceCodeWindow').then(m => ({ default: m.SourceCodeWindow })));
const PythonCodeEditor = lazy(() => import('./PythonCodeEditor').then(m => ({ default: m.PythonCodeEditor })));
import type { PreviewSnapshot } from './PreviewStudio';
import { SourceComponentLibrary } from './SourceComponentLibrary';

type Port = { node: string; port: string; label: string };
type Node = { id: string; label: string; kind: string; parent: string | null; constructor?: unknown; arguments?: unknown; module?: { source: string; entry: string; constructor: Record<string, unknown> }; ports: { inputs: Port[]; outputs: Port[] } };
export type SummaryAuthoringState = {
  workspaceId: string; title: string; scope: string | null; nodes: Node[];
  edges: { id: string; source: string; target: string; source_port: string; target_port: string }[];
  library: { title: string }[]; sourceNodes: { id: string; label: string; kind: string }[];
  recipe?: { level: string; parts: { index: number; title: string; nodes: number; present: boolean }[]; pendingConnections: number; readyConnections: number; exact: boolean } | null;
  edited?: boolean; localAnalysis?: { contracts: number } | null;
};
type Preset = { title: string; level?: string };

/** Retain Studio's inspector sections; the iframe alone owns editable facts. */
export function SummaryAuthoringPanel({ snapshot, selected, disabled, onEdit, onFormal, onCompile, onCertify }: {
  snapshot: PreviewSnapshot | null; selected: string[]; disabled: boolean;
  onEdit: (operation: Record<string, unknown>) => Promise<void>; onFormal: () => void;
  onCompile: (value: { source: string; entry: string; constructor: Record<string, unknown> }) => Promise<Record<string, unknown>>;
  onCertify: (ir: Record<string, unknown>) => Promise<Record<string, unknown>>;
}) {
  const state = snapshot?.authoring as SummaryAuthoringState | undefined;
  const reference = (snapshot?.nativeDocument as { document?: { codeReference?: { source: string; entry: string; constructor: Record<string, unknown> } } } | undefined)?.document?.codeReference;
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  const [presets, setPresets] = useState<Preset[]>([]), [query, setQuery] = useState('');
  const [name, setName] = useState('CustomGroup'), [from, setFrom] = useState(''), [to, setTo] = useState(''), [replace, setReplace] = useState(false);
  const [label, setLabel] = useState(''), [fields, setFields] = useState('{}');
  const [edgeId, setEdgeId] = useState('');
  const [modelTitle, setModelTitle] = useState(state?.title ?? '');
  const [moduleSource, setModuleSource] = useState(reference?.source ?? 'from torch import nn\n\nclass CustomBlock(nn.Module):\n    def __init__(self, width=8):\n        super().__init__()\n        self.linear = nn.Linear(width, width)\n\n    def forward(self, x):\n        return self.linear(x)\n');
  const [moduleEntry, setModuleEntry] = useState(reference?.entry ?? 'CustomBlock'), [moduleConfig, setModuleConfig] = useState(reference ? JSON.stringify(reference.constructor, null, 2) : '{"width":8}');
  const [recipeAtomic, setRecipeAtomic] = useState(false);
  const [section, setSection] = useState<'add' | 'selection' | 'advanced'>('add');
  const [sourceLibraryOpen, setSourceLibraryOpen] = useState(false);
  const [connectionsOpen, setConnectionsOpen] = useState(false);
  const [sourceWindowOpen, setSourceWindowOpen] = useState(false);
  const [generated, setGenerated] = useState<Awaited<ReturnType<typeof api.summaryPython>> | null>(null);
  const [generatedFile, setGeneratedFile] = useState('generated_model.py');
  const [generatedDocument, setGeneratedDocument] = useState('');
  const chosen = state?.nodes.filter(n => selected.includes(n.id)) ?? [], node = chosen.length === 1 ? chosen[0] : undefined;
  useEffect(() => {
    setLabel(node?.label ?? ''); setFields(JSON.stringify({ constructor: node && Object.hasOwn(node, 'constructor') ? node.constructor : {}, arguments: node?.arguments ?? {} }, null, 2));
  }, [node?.id, node?.label, JSON.stringify(node?.constructor), JSON.stringify(node?.arguments)]);
  useEffect(() => setModelTitle(state?.title ?? ''), [state?.title]);
  useEffect(() => { if (node?.module) { setModuleSource(node.module.source); setModuleEntry(node.module.entry); setModuleConfig(JSON.stringify(node.module.constructor, null, 2)); } }, [node?.id, node?.module?.source, JSON.stringify(node?.module?.constructor)]);
  useEffect(() => {
    let live = true;
    void fetch('/preview/data/semantic/authoring-presets.json').then(r => { if (!r.ok) throw Error('构件库读取失败'); return r.json(); }).then(value => { if (live) setPresets(value.modules); }).catch(e => { if (live) setError(String(e)); });
    return () => { live = false; };
  }, []);
  if (!state) return null;
  const locked = disabled || pending;
  const byId = new Map(state.nodes.map(n => [n.id, n]));
  const scopeNode = state.scope ? byId.get(state.scope) : undefined;
  const scopeOptions = state.nodes.filter(n => n.kind === 'composite' && (n.id === state.scope || n.parent === state.scope || n.id === scopeNode?.parent));
  async function run(operation: Record<string, unknown>) {
    setPending(true); setError('');
    try { await onEdit(operation); } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  async function compile(replaceModule: boolean, asModel = false) {
    setPending(true); setError('');
    // Pin this request to its starting workspace/selection. The App callback
    // also rejects a source response if the user loaded another model meanwhile.
    const id = node?.id, workspaceId = state!.workspaceId, baseDocumentSha256 = (snapshot?.nativeDocument as { documentSha256?: string } | undefined)?.documentSha256;
    try {
      const constructor = JSON.parse(moduleConfig);
      if (!constructor || typeof constructor !== 'object' || Array.isArray(constructor)) throw Error('构造参数必须是 JSON 对象');
      const module = await onCompile({ source: moduleSource, entry: moduleEntry, constructor });
      await onEdit({ action: asModel ? 'import-source-model' : replaceModule ? 'replace-module' : 'add-source', ...(replaceModule ? { id } : {}), workspaceId, baseDocumentSha256, module });
      if (asModel) setSourceWindowOpen(false);
    } catch (e) { setError(String(e)); throw e; } finally { setPending(false); }
  }
  async function exportPython() {
    setPending(true); setError('');
    try {
      const document = (snapshot?.nativeDocument as { document?: Record<string, unknown> } | undefined)?.document;
      if (!document) throw Error('当前组装视图尚未就绪。');
      const result = await api.summaryPython(document);
      setGenerated(result); setGeneratedFile('generated_model.py'); setGeneratedDocument(JSON.stringify(document));
    } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  async function certify() {
    setPending(true); setError('');
    const workspaceId = state!.workspaceId, baseDocumentSha256 = (snapshot?.nativeDocument as { documentSha256?: string } | undefined)?.documentSha256;
    try {
      const generic = snapshot?.graph?.generic as { ir?: Record<string, unknown> } | undefined;
      if (!generic?.ir) throw Error('当前组装视图尚未就绪。');
      const ir = generic.ir;
      const result = await onCertify(ir);
      await onEdit({ action: 'certify', workspaceId, baseDocumentSha256, result });
    } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  const match = (value: string) => value.toLowerCase().includes(query.toLowerCase());
  const ports = (direction: 'inputs' | 'outputs') => {
    const found = new Map<string, { value: string; label: string }>();
    for (const n of state.nodes.filter(n => n.parent === state.scope)) for (const p of n.ports[direction]) {
      const value = JSON.stringify({ node: p.node, port: p.port });
      if (!found.has(value)) found.set(value, { value, label: `${n.label} · ${p.label} [${p.port}] · ${p.node}` });
    }
    return [...found.values()];
  };
  const outputs = section === 'selection' && connectionsOpen ? ports('outputs') : [], inputs = section === 'selection' && connectionsOpen ? ports('inputs') : [];
  const validPorts = outputs.some(p => p.value === from) && inputs.some(p => p.value === to);
  return <div className="summary-authoring-panel">
    <button className="full-button" disabled={locked} onClick={() => setSourceWindowOpen(true)}>{t('打开悬浮源码工作台')}</button>
    {sourceWindowOpen && <Suspense fallback={<p>Monaco…</p>}><SourceCodeWindow source={moduleSource} entry={moduleEntry} config={moduleConfig} onSource={setModuleSource} onEntry={setModuleEntry} onConfig={setModuleConfig} onClose={() => setSourceWindowOpen(false)} onApply={mode => compile(mode === 'replace', mode === 'model')} busy={locked} canReplace={!!node} /></Suspense>}
    <p className="field-help authoring-intro">{t("编辑独立副本，原始源码保留。组装变更尚未执行验证。")}</p>
    {error && <p role="alert">{uiMessage(error)}</p>}
    <details className="inspector-section authoring-model-name" open><summary>{t("模型信息与名称")}</summary><label className="field-label">{t("模型名称")}<input aria-label={t("Summary 模型名称")} maxLength={240} value={modelTitle} onChange={e => setModelTitle(e.target.value)} /></label><button disabled={locked || !modelTitle.trim() || modelTitle === state.title} onClick={() => void run({ action: 'title', title: modelTitle })}>{t("应用模型名称")}</button><p className="field-help">{t("副本保存到浏览器；编辑 JSON 可搬运完整内容。")}</p></details>

    <section className="authoring-scope"><label className="field-label">{t("插入与连接层级")}<select aria-label={t("Summary 编辑层级")} value={state.scope ?? ''} disabled={locked} onChange={e => void run({ action: 'scope', id: e.target.value || null })}><option value="">{t("模型顶层")}</option>{scopeOptions.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}</select></label>
      <button disabled={locked || !state.scope} onClick={() => void run({ action: 'scope', id: scopeNode?.parent ?? null })}>{t("返回上一级")}</button>
      <p className="field-help">{scopeNode ? t("当前：{0}", {"0": scopeNode.label}) : t("新构件加入模型顶层；选择模块可进入其内部。")}</p>
    </section>
    <div className="authoring-tabs" role="group" aria-label={t("构件编辑分组")}>{([{id:'add',label:t("添加")}, {id:'selection',label:t("选中{0}", {"0": chosen.length ? ` · ${chosen.length}` : ''})}, {id:'advanced',label:t("高级")}] as const).map(item => <button aria-pressed={section === item.id} key={item.id} onClick={() => setSection(item.id)}>{item.label}</button>)}</div>
    <div className="authoring-tabpanel">
    {section === 'add' && <>
    <section className="authoring-interfaces"><h3>{t("模型接口")}</h3><div className="segmented"><button disabled={locked} onClick={() => void run({ action: 'interface', role: 'input', label: 'input' })}>{t("添加输入")}</button><button disabled={locked} onClick={() => void run({ action: 'interface', role: 'output', label: 'output' })}>{t("添加输出")}</button></div></section>
    <section className="inspector-section authoring-component-search">
      <input aria-label={t("搜索 Summary 构件")} placeholder={t("搜索模块、算子或源码构件…")} value={query} onChange={e => setQuery(e.target.value)} />
    </section>
    <details className="inspector-section" open><summary>{t("基础构件")}</summary>
      <div className="summary-authoring-library">{presets.map((m, index) => ({ ...m, index })).filter(m => match(m.title)).map(m => <button key={m.index} className="full-button" disabled={locked} onClick={() => void run({ action: 'add', preset: m.index })}>{m.title}{m.level === 'atomic' ? t(" · 原子") : ''}</button>)}</div>
      <details><summary>{t("我的组合模块（{0}）", {"0": state.library.length})}</summary>{state.library.map((m, i) => <button key={i} className="full-button" disabled={locked} onClick={() => void run({ action: 'add', library: i })}>{m.title}</button>)}</details>
    </details>
    <details className="inspector-section" open={sourceLibraryOpen} onToggle={e => setSourceLibraryOpen(e.currentTarget.open)}><summary>{t("原始源码构件库")}</summary>{sourceLibraryOpen && <SourceComponentLibrary query={query} disabled={locked} onAdd={(id, scope) => void run({ action: 'add', sourceComponent: id, ...(scope ? { componentScope: scope } : {}) })} />}</details>
    </>}
    {(section === 'add' || section === 'selection') && <>
    <details className="inspector-section"><summary>{t("源码模块与参数重解析")}</summary><p className="field-help">{t("保留源码文本与构造参数，静态提取 Summary 模块。替换选中构件时按同名接口保留连接；移除已连接接口会拒绝，原稿可继续编辑。")}</p>
      <label className="field-label">{t("模块入口")}<input aria-label={t("Summary 模块入口")} value={moduleEntry} onChange={e => setModuleEntry(e.target.value)} /></label>
      <label className="field-label">{t("构造参数")}<textarea aria-label={t("Summary 模块构造参数")} rows={4} value={moduleConfig} onChange={e => setModuleConfig(e.target.value)} /></label>
      <button className="full-button" disabled={locked} onClick={() => setSourceWindowOpen(true)}>{t("打开悬浮源码工作台")}</button><pre className="source-code-preview">{moduleSource}</pre>
      <div className="segmented"><button disabled={locked || !moduleSource.trim() || !moduleEntry.trim()} onClick={() => void compile(false).catch(() => {})}>{t("解析并加入源码模块")}</button><button disabled={locked || !node} onClick={() => void compile(true).catch(() => {})}>{t("重新解析并替换选中构件")}</button></div>
      <p className="field-help">{t("此操作只更新组装稿。Python 不执行，也不写回原始模型。")}</p>
    </details>
    </>}
    {section === 'selection' && <>
    <details className="inspector-section" open><summary>{t("节点与结构编辑")}</summary><p className="field-help">{t("已选")}{chosen.length}{t("个原始节点。合并图元请先展开，再编辑具体构件。")}</p>
      {node && <><label className="field-label">{t("节点名称")}<input aria-label={t("Summary 节点名称")} value={label} onChange={e => setLabel(e.target.value)} /></label><button disabled={locked || !label.trim()} onClick={() => void run({ action: 'edit', id: node.id, fields: { label } })}>{t("应用节点名称")}</button>
        <details><summary>{t("参数声明")}</summary><textarea aria-label={t("Summary 参数声明")} rows={6} value={fields} onChange={e => setFields(e.target.value)} /><button disabled={locked} onClick={() => { try { void run({ action: 'edit', id: node.id, fields: JSON.parse(fields) }); } catch (e) { setError(String(e)); } }}>{t("应用参数声明")}</button><p className="field-help">{t("声明不改写 Python。更新模块的源码事实请使用“源码模块与参数重解析”。")}</p></details></>}
      <div className="segmented"><button disabled={locked || !chosen.length} onClick={() => void run({ action: 'duplicate', ids: chosen.map(n => n.id) })}>{t("复制选中构件")}</button><button disabled={locked || !chosen.length} onClick={() => void run({ action: 'erase', ids: chosen.map(n => n.id) })}>{t("删除选中构件")}</button></div>
      <label className="field-label">{t("组合名称")}<input aria-label={t("Summary 组合名称")} maxLength={240} value={name} onChange={e => setName(e.target.value)} /></label>
      <div className="segmented"><button disabled={locked || !chosen.length || !name.trim()} onClick={() => void run({ action: 'group', ids: chosen.map(n => n.id), title: name })}>{t("组合为模块")}</button><button disabled={locked || !chosen.length || !name.trim()} onClick={() => void run({ action: 'library', ids: chosen.map(n => n.id), title: name })}>{t("保存组合到库")}</button></div>
    </details>
    <details className="inspector-section" open={connectionsOpen} onToggle={e => setConnectionsOpen(e.currentTarget.open)}><summary>{t("精确槽位连接")}</summary>{connectionsOpen && <><p className="field-help">{t("当前编辑层级的真实 producer / consumer 槽位。输入已有驱动时需要明确选择替换。")}</p>
      <label className="field-label">{t("输出槽位")}<select aria-label={t("Summary 输出槽位")} disabled={locked} value={outputs.some(p => p.value === from) ? from : ''} onChange={e => setFrom(e.target.value)}><option value="">{t("选择输出")}</option>{outputs.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}</select></label>
      <label className="field-label">{t("输入槽位")}<select aria-label={t("Summary 输入槽位")} disabled={locked} value={inputs.some(p => p.value === to) ? to : ''} onChange={e => setTo(e.target.value)}><option value="">{t("选择输入")}</option>{inputs.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}</select></label>
      <label><input type="checkbox" checked={replace} onChange={e => setReplace(e.target.checked)} />{t("明确替换输入已有连接")}</label>
      <button disabled={locked || !validPorts} onClick={() => void run({ action: 'connect', source: JSON.parse(from), target: JSON.parse(to), replace })}>{t("建立精确连接")}</button>
      <label className="field-label">{t("原始依赖")}<select aria-label={t("Summary 原始依赖")} value={state.edges.some(e => e.id === edgeId) ? edgeId : ''} disabled={locked} onChange={e => setEdgeId(e.target.value)}><option value="">{t("选择一条原始依赖")}</option>{state.edges.map(e => <option key={e.id} value={e.id}>{e.source}[{e.source_port}] → {e.target}[{e.target_port}]</option>)}</select></label>
      <div className="segmented"><button disabled={locked || !state.edges.some(e => e.id === edgeId)} onClick={() => void run({ action: 'remove-edge', id: edgeId })}>{t("删除原始依赖")}</button><button disabled={locked || !validPorts || !state.edges.some(e => e.id === edgeId)} onClick={() => void run({ action: 'rewire', id: edgeId, source: JSON.parse(from), target: JSON.parse(to), replace })}>{t("重接原始依赖")}</button></div>
      </>}
    </details>
    </>}
    {section === 'advanced' && <>
    <details className="inspector-section" open><summary>{t('生成可执行 Python')}</summary><p className="field-help">{t('支持精确源码重建及通过接口连接的源码构件。内部原子修改、缺失连接或未知结构会拒绝导出；生成时不执行代码。')}</p><button disabled={locked} onClick={() => void exportPython()}>{t('校验当前图并生成 Python')}</button>
      {generated && <><p className="field-help">{generated.entry} · {generated.mode}</p>{generatedDocument !== JSON.stringify((snapshot?.nativeDocument as {document?: unknown})?.document) ? <p role="status">{t('编辑稿已变化，请重新生成。')}</p> : <><select aria-label={t('生成的 Python 文件')} value={generatedFile} onChange={e => setGeneratedFile(e.target.value)}>{Object.keys(generated.files).map(file => <option key={file}>{file}</option>)}</select><div className="source-code-output"><Suspense fallback={<p>Monaco…</p>}><PythonCodeEditor value={generated.files[generatedFile]} onChange={() => {}} readOnly /></Suspense></div><button onClick={() => { const bytes = Uint8Array.from(atob(generated.archiveBase64), char => char.charCodeAt(0)); const url = URL.createObjectURL(new Blob([bytes], {type:'application/zip'})); const link = document.createElement('a'); link.href = url; link.download = 'archcanvas-python.zip'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>{t('下载 Python 项目')}</button></>}</>}
    </details>
    <details className="inspector-section"><summary>{t("原始构件精确重建")}</summary><p className="field-help">{t("从原始参考 IR 分解为构件，再逐个恢复原身份和跨构件槽位连接。开始后当前搭建可撤销；完整重建后可生成保留源码的 Python；此步骤不执行代码。")}</p>
      <label><input type="checkbox" checked={recipeAtomic} onChange={e => setRecipeAtomic(e.target.checked)} />{t("按源码原子逐个重建")}</label>
      <button disabled={locked || !state.sourceNodes.length} onClick={() => void run({ action: 'recipe-start', atomic: recipeAtomic })}>{t("清空搭建并开始参考重建")}</button>
      {state.recipe && <><p className="field-help">{state.recipe.parts.length}{t("个参考构件 ·")}{state.recipe.pendingConnections}{t("条跨构件连接待恢复")}{state.recipe.exact ? t(" · 原始节点与依赖已精确重建") : ''}</p>
        <div className="summary-authoring-library">{state.recipe.parts.map(p => <button key={p.index} className="full-button" disabled={locked || p.present} onClick={() => void run({ action: 'recipe-add', part: p.index })}>{p.present ? t("已加入 · ") : t("恢复构件 · ")}{p.title}（{p.nodes}）</button>)}</div>
        <button disabled={locked || !state.recipe.readyConnections} onClick={() => void run({ action: 'recipe-wires' })}>{t("恢复现有端点的精确连接")}</button></>}
    </details>
    <details className="inspector-section"><summary>{t("组装局部结构复核")}</summary><p className="field-help">{t("检查当前组装稿的操作数关系，重新识别可用的局部语义契约。结果只覆盖声明结构；不表示 Python 等价、shape 兼容或模型执行通过。")}</p>
      <button disabled={locked || !state.edited} onClick={() => void certify()}>{t("复核当前组装结构")}</button>
      {state.localAnalysis ? <p className="field-help" role="status">{t("已保存局部结构结果：")}{state.localAnalysis.contracts}{t("项契约；文档来源，模型未执行。结构编辑后需重新复核。")}</p> : <p className="field-help">{state.edited ? t("当前组装稿尚无局部结构复核结果。") : t("当前为原始参考事实；结构编辑后可复核组装稿。")}</p>}
    </details>
    <details className="inspector-section"><summary>{t("正式源码编辑")}</summary><p className="field-help">{t("组装声明不授予源码事务权限。Python 工作副本仍使用受管理的解析、审查和提交流程。")}</p><button disabled={locked} onClick={onFormal}>{t("打开正式源码工作副本")}</button></details>
    </>}
    </div>
  </div>;
}
