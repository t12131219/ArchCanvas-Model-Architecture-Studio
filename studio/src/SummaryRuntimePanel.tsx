import { useEffect, useRef, useState } from 'react';
import type { SummaryRuntimeResult } from './api';

type Fact = Record<string, unknown>;
const record = (value: unknown): Fact => value && typeof value === 'object' && !Array.isArray(value) ? value as Fact : {};
const initial = { schema: 'semantic-inputs/1', constructor: {}, modes: ['eval'], cases: [{ id: 'sample', seed: 0, inputs: {} }] };

/** Retained Studio form; execution and observed graph live in their authorities. */
export function SummaryRuntimePanel({ available, reason, hasSource, storedReceipt, disabled, onRun, onOpen }: {
  available: boolean; reason?: string; hasSource: boolean; storedReceipt?: unknown; disabled: boolean;
  onRun: (spec: Fact, onStart: (cancel: () => Promise<void>) => void) => Promise<SummaryRuntimeResult>;
  onOpen: (result: SummaryRuntimeResult) => Promise<void>;
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
  return <details className="inspector-section summary-runtime">
    <summary>新 CPU 观察<span className="read-only">显式样例</span></summary>
    <p className="field-help">记录实际执行的算子、张量来源和源码位置。填写明确的输入、构造参数和模式，再运行 CPU 样例；结果独立保留。</p>
    {!available && <p className="field-help">隔离 CPU 环境不可用：{reason || '未通过运行环境检查'}</p>}
    {!hasSource && <p className="field-help">当前文档没有可用的 Python 文本，仍可查看已有运行记录。</p>}
    <label className="field-label">CPU 样例规格<textarea aria-label="Summary CPU 输入规格" rows={12} spellCheck={false} value={draft} disabled={pending} onChange={e => setDraft(e.target.value)} /></label>
    <p className="field-help">在 cases[].inputs 中填写具名输入，例如 x: {'{"shape":[2,3],"dtype":"float32","fill":"ones"}'}；标量使用 {'{"value":true}'}。模式可选 eval / train，seed 明确随机种子。</p>
    <button className="full-button" disabled={disabled || pending || !available || !hasSource} onClick={() => void run()}>{pending ? '正在隔离运行…' : '运行 CPU 观察'}</button>
    {pending && <button className="full-button" onClick={() => { stopRequested.current = true; void cancel.current?.().catch(e => { if (alive.current) setError(String(e)); }); }}>取消 CPU 观察</button>}
    {!!Object.keys(receipt).length && <>
      <p className="field-help">状态：{String(receipt.status ?? '未知')} · {receipt.model_executed === true ? '已执行声明样例' : receipt.model_executed === false ? '未执行模型' : '执行未完整确认'} · {runs.length} 条运行记录{receipt.reason ? ` · ${String(receipt.reason)}` : ''}</p>
      <p className="field-help">样例观察不证明所有输入或未观察分支，也不授予源码写回权限。</p>
      <details onToggle={event => setShowReceipt(event.currentTarget.open)}><summary>输入、环境与完整观察收据</summary>{showReceipt && <pre>{JSON.stringify(receipt, null, 2)}</pre>}</details>
    </>}
    {result?.document && <button className="full-button" disabled={disabled || pending} onClick={() => { setError(''); void onOpen(result).catch(e => { if (alive.current) setError(String(e)); }); }}>打开本次观察结果</button>}
    {error && <p className="field-help error" role="alert">{error}</p>}
  </details>;
}
