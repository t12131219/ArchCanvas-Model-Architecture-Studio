import { useState } from 'react';
import type { Architecture, CanvasDocument } from './core';
import type { Binding, RebindOptions } from './api';

export function ConnectionEditor({ document, nodeId, portId, enabled, busy, onInspect, onPrepare }: {
  document: CanvasDocument; nodeId: string; portId: string; enabled: boolean; busy: boolean;
  onInspect: (nodeId: string, portId: string) => Promise<RebindOptions>;
  onPrepare: (nodeId: string, portId: string, producer: Binding) => void;
}) {
  const [options, setOptions] = useState<RebindOptions | null>(null);
  const [candidate, setCandidate] = useState('');
  const [error, setError] = useState('');
  const edge = document.architecture.edges.find(e => e.target.nodeId === nodeId && e.target.portId === portId);
  const portName = document.architecture.nodes.find(n => n.id === nodeId)?.ports.find(p => p.id === portId)?.name ?? '输入';
  const label = (binding?: Binding) => binding ? bindingLabel(document.architecture, document, binding) : '未解析';
  const selected = options?.candidates.find(c => `${c.binding.nodeId}:${c.binding.portId}` === candidate);
  const current = options?.target?.currentBinding;
  const unchanged = selected && current && selected.binding.nodeId === current.nodeId && selected.binding.portId === current.portId;
  async function inspect() {
    setError('');
    try {
      const result = await onInspect(nodeId, portId); setOptions(result);
      const first = result.candidates.find(c => c.binding.nodeId !== result.target?.currentBinding.nodeId || c.binding.portId !== result.target?.currentBinding.portId);
      setCandidate(first ? `${first.binding.nodeId}:${first.binding.portId}` : '');
    } catch (e) { setError(String(e)); }
  }
  return <section className="property-section semantic-editor connection-editor">
    <h3>输入连接<span className="review-tag">先审核</span></h3>
    <div className="binding-card"><small>当前来源 · {portName}</small><strong>{label(edge ? { ...edge.source, tensorId: edge.tensorId } : undefined)}</strong></div>
    <button className="full-button" disabled={!enabled || busy} onClick={() => void inspect()}>{options ? '重新检查可选来源' : '检查连接编辑能力'}</button>
    {options && <>
      {options.target && <p className="field-help">源码输入：<code>{options.target.slot.variable}</code> · {options.target.slot.path}:{options.target.slot.line}</p>}
      {options.supported && options.candidates.length > 0 && <>
        <label className="field-label" htmlFor="rebind-producer">新的输入来源</label>
        <select id="rebind-producer" aria-label="新的输入来源" className="field-select" value={candidate} disabled={busy} onChange={e => setCandidate(e.target.value)}>
          <option value="" disabled>选择可用来源</option>
          {options.candidates.map(c => <option key={`${c.binding.nodeId}:${c.binding.portId}`} value={`${c.binding.nodeId}:${c.binding.portId}`}>{label(c.binding)} · {c.variable}{c.binding.nodeId === current?.nodeId && c.binding.portId === current.portId ? '（当前）' : ''}</option>)}
        </select>
        <p className="field-help">同一输入的符号形状与类型；来源在调用前已定义。运行时未验证，改接会改变计算行为。</p>
        {selected && <details className="connection-contract"><summary>兼容性条件</summary><p>{selected.contract.condition}</p><code>{selected.contract.shape.identity}<br />{selected.contract.dtype.identity}</code></details>}
        <button className="full-button" disabled={busy || !selected || !!unchanged} onClick={() => selected && onPrepare(nodeId, portId, selected.binding)}>预览连接修改</button>
      </>}
      {(!options.supported || !options.candidates.length) && <p className="field-help"><b>连接提案暂不可提交</b></p>}
      {!!options.blockers.length && <div className="connection-blockers">{options.blockers.map((b, i) => <p key={i}>{b}</p>)}</div>}
    </>}
    {!options && <p className="field-help">检查精确源码参数、作用域及兼容性，再生成工作副本的连接修改预览。</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
  </section>;
}

export function bindingLabel(architecture: Architecture, document: CanvasDocument, binding: Binding) {
  const node = architecture.nodes.find(n => n.id === binding.nodeId);
  return document.displayAliases[binding.nodeId] ?? node?.label ?? binding.nodeId;
}
