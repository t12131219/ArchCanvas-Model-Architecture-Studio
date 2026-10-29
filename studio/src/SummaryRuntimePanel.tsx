import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PreviewSnapshot } from './PreviewStudio';
import type { SummaryRuntimeResult } from './api';

type Fact = Record<string, unknown>;
const record = (value: unknown): Fact => value && typeof value === 'object' && !Array.isArray(value) ? value as Fact : {};
const initial = { schema: 'semantic-inputs/1', constructor: {}, modes: ['eval'], cases: [{ id: 'sample', seed: 0, inputs: {} }] };

/** Retained Studio form; execution and observed graph live in their authorities. */
export function SummaryRuntimePanel({ available, reason, hasSource, storedReceipt, disabled, onRun, snapshot, selectedIds = [], onCommand, onSaveEvidence, children }: {
  available: boolean; reason?: string; hasSource: boolean; storedReceipt?: unknown; disabled: boolean;
  onRun: (spec: Fact, onStart: (cancel: () => Promise<void>) => void) => Promise<SummaryRuntimeResult>;
  onSaveEvidence: (document: Record<string, unknown>) => void;
  snapshot?: PreviewSnapshot | null; selectedIds?: string[]; children?: ReactNode;
  onCommand?: (payload: Record<string, unknown>) => void;
}) {
  const previous = record(storedReceipt);
  const [draft, setDraft] = useState(JSON.stringify(previous.input_spec ?? initial, null, 2));
  const [showReceipt, setShowReceipt] = useState(false);
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [result, setResult] = useState<SummaryRuntimeResult | null>(null);
  const stopRequested = useRef(false);
  const alive = useRef(true), cancel = useRef<(() => Promise<void>) | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; void cancel.current?.().catch(() => {}); }; }, []);
  async function run() {
    setError(''); setPending(true); setResult(null); stopRequested.current = false;
    try {
      const value = JSON.parse(draft);
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('输入规格须为 JSON 对象。');
      const next = await onRun(value, stop => { cancel.current = stop; if (!alive.current || stopRequested.current) void stop().catch(() => {}); });
      if (alive.current) setResult(next);
    } catch (e) { if (alive.current) setError(String(e)); }
    finally { cancel.current = null; if (alive.current) setPending(false); }
  }
  const receipt = record(result?.receipt ?? storedReceipt), runs = Array.isArray(receipt.runs) ? receipt.runs : [];
  const view = snapshot?.semanticView as { mode?: string; legacy?: boolean;
    runtimeEvidence?: { runs: { index: number; case: string; mode: string; status: string }[]; selectedRun: number; integratedRegions: number; unplacedRegions: number };
    selectionDetails?: { id: string; evidence: string }[];
    nodeAccounting?: Record<string, string[]>; edgeAccounting?: Record<string, string[]>;
  } | undefined;
  const evidence = view?.runtimeEvidence, observed = evidence?.runs ?? [], mode = view?.mode ?? 'source';
  const patch = (value: Record<string, unknown>) => onCommand?.({ patch: value });
  return <details className="inspector-section summary-runtime">
    <summary>源码与运行证据<span className="read-only">来源与覆盖</span></summary>
    {mode === 'runtime' && <><p className="field-help">当前打开的是旧版轨迹文档。</p><button className="full-button" disabled={disabled} onClick={() => patch({ mode: 'merged', paperFocus: null, paperRelation: null })}>回到源码主图</button></>}
    {!!observed.length && <>
      <label className="check"><input type="checkbox" aria-label="显示已匹配运行证据" checked={mode === 'merged'} disabled={disabled} onChange={event => patch({ mode: event.target.checked ? 'merged' : 'source', paperFocus: null, paperRelation: null })}/>显示已匹配运行证据</label>
      <label className="field-label">观察记录<select aria-label="Summary 观察记录" disabled={disabled} value={evidence?.selectedRun ?? 0} onChange={event => patch({ mode: 'merged', runtimeInlineRun: Number(event.target.value), paperFocus: null })}>
        {observed.map(run => <option key={run.index} value={run.index}>{run.case} / {run.mode} · {run.status === 'passed' ? '记录通过' : run.status === 'failed' ? '记录失败' : run.status}</option>)}
      </select></label>
      <p className="field-help">{observed.length} 条文档内观察记录；{mode === 'merged' ? `${evidence?.integratedRegions ?? 0} 个调用已匹配到当前源码。` : '可在当前图中显示匹配结果。'} 未观察路径仍为未知。</p>
      <details><summary>观察记录与匹配范围</summary><pre>{JSON.stringify(evidence, null, 2)}</pre></details>
    </>}
    {!observed.length && <p className="field-help">当前没有可匹配的运行记录，按已有源码或登记证据展示。探针只补充明确样例实际经过的路径。</p>}
    {view?.selectionDetails?.filter(detail => selectedIds.includes(detail.id)).map(detail => <details key={detail.id}><summary>所选对象的源码与证据</summary><pre>{detail.evidence}</pre></details>)}
    {children}
    <details className="summary-probe"><summary>添加运行证据</summary>
      <p className="field-help">使用明确的输入、构造参数和模式运行隔离 CPU 探针，检查未知模块及实际执行路径。</p>
      {!available && <p className="field-help">隔离 CPU 环境不可用：{reason || '未通过运行环境检查'}</p>}
      {!hasSource && <p className="field-help">当前文档没有可执行的 Python 文本，可继续查看已有运行记录。</p>}
      {available && hasSource && <>
        <label className="field-label">输入规格<textarea aria-label="Summary CPU 输入规格" rows={10} spellCheck={false} value={draft} disabled={pending} onChange={e => setDraft(e.target.value)} /></label>
        <p className="field-help">cases[].inputs 填写具名输入，例如 x: {'{"shape":[2,3],"dtype":"float32","fill":"ones"}'}；标量使用 {'{"value":true}'}。模式可选 eval / train。</p>
        <button className="full-button" disabled={disabled || pending} onClick={() => void run()}>{pending ? '正在隔离运行…' : '运行探针'}</button>
      </>}
      {pending && <button className="full-button" onClick={() => { stopRequested.current = true; void cancel.current?.().catch(e => { if (alive.current) setError(String(e)); }); }}>取消运行探针</button>}
      {!!Object.keys(receipt).length && <>
        <p className="field-help">状态：{String(receipt.status ?? '未知')} · {receipt.model_executed === true ? '已执行声明样例' : receipt.model_executed === false ? '未执行模型' : '执行未完整确认'} · {runs.length} 条运行记录{receipt.reason ? ` · ${String(receipt.reason)}` : ''}</p>
        <details onToggle={event => setShowReceipt(event.currentTarget.open)}><summary>输入、环境与完整观察收据</summary>{showReceipt && <pre>{JSON.stringify(receipt, null, 2)}</pre>}</details>
      </>}
      {result?.document && <><button className="full-button" onClick={() => onSaveEvidence(result.document!)}>保存本次观察证据</button><p className="field-help">本次结果尚未附加到当前图。请保存证据文档；切换模型或关闭面板后，本次临时结果会清除。</p></>}
      {error && <p className="field-help error" role="alert">{error}</p>}
    </details>
    {!!view?.nodeAccounting && <details><summary>原始节点与依赖归属</summary><pre>{JSON.stringify({ nodes: Object.fromEntries(Object.entries(view.nodeAccounting).map(([key, ids]) => [key, ids.length])), edges: Object.fromEntries(Object.entries(view.edgeAccounting ?? {}).map(([key, ids]) => [key, ids.length])) }, null, 2)}</pre></details>}
    <p className="field-help">运行证据对应特定输入和模式，不证明未观察分支。源码修改仍通过正式编辑与事务审查。</p>
  </details>;
}
