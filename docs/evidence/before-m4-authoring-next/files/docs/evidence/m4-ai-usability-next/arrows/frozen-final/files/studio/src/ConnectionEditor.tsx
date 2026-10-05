import { useEffect, useState } from 'react';
import type { Architecture, CanvasDocument } from './core';
import type { Binding, InputSpec, RebindOptions } from './api';

export function ConnectionEditor({ document, nodeId, portId: initialPortId, enabled, busy, inputSpec, onSetup, onInspect, onPrepare }: {
  document: CanvasDocument; nodeId: string; portId: string; enabled: boolean; busy: boolean; inputSpec: InputSpec | null; onSetup: () => void;
  onInspect: (nodeId: string, portId: string) => Promise<RebindOptions>;
  onPrepare: (nodeId: string, portId: string, producer: Binding) => void;
}) {
  const ports = document.architecture.nodes.find(n => n.id === nodeId)?.ports.filter(p => p.direction === 'in') ?? [];
  const [portId, setPort] = useState(initialPortId);
  const [options, setOptions] = useState<RebindOptions | null>(null);
  const [candidate, setCandidate] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { setOptions(null); setCandidate(''); setError(''); }, [portId]);
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
    {ports.length > 1 && <><label className="field-label" htmlFor="rebind-target-port">目标输入端口</label><select id="rebind-target-port" aria-label="目标输入端口" className="field-select" value={portId} onChange={e => setPort(e.target.value)} disabled={busy}>{ports.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></>}
    <div className="binding-card"><small>当前来源 · {portName}</small><strong>{label(edge ? { ...edge.source, tensorId: edge.tensorId } : undefined)}</strong></div>
    <button className="full-button" onClick={onSetup} disabled={busy}>{inputSpec ? '调整运行输入与模式' : '设置运行输入与模式'}</button>
    {inputSpec && <p className="field-help">CPU · {inputSpec.modes.join(' / ')} · 随机种子 {inputSpec.seed}</p>}
    <button className="full-button" disabled={!enabled || busy || !inputSpec} onClick={() => void inspect()}>{options ? '重新检查可选来源' : '检查连接编辑能力'}</button>
    {options && <>
      {options.target && <p className="field-help">源码输入：<code>{options.target.slot.variable}</code> · {options.target.slot.path}:{options.target.slot.line}</p>}
      {options.supported && options.candidates.length > 0 && <>
        <label className="field-label" htmlFor="rebind-producer">新的输入来源</label>
        <select id="rebind-producer" aria-label="新的输入来源" className="field-select" value={candidate} disabled={busy} onChange={e => setCandidate(e.target.value)}>
          <option value="" disabled>选择可用来源</option>
          {options.candidates.map(c => <option key={`${c.binding.nodeId}:${c.binding.portId}`} value={`${c.binding.nodeId}:${c.binding.portId}`}>{label(c.binding)} · {c.variable}{c.binding.nodeId === current?.nodeId && c.binding.portId === current.portId ? '（当前）' : ''}</option>)}
        </select>
        <p className="field-help">来源在调用前已定义。预览会在隔离环境中验证输入合同、前向、梯度和状态；改接会改变计算行为。</p>
        {selected && <details className="connection-contract"><summary>兼容性条件</summary><p>{selected.contract.condition}</p><code>{Array.isArray(selected.contract.shape) ? `[${selected.contract.shape.join(', ')}] · ${selected.contract.dtype}` : '符号签名'}</code></details>}
        <button className="full-button" disabled={busy || !selected || !!unchanged || !inputSpec} onClick={() => selected && onPrepare(nodeId, portId, selected.binding)}>运行验证并预览连接修改</button>
      </>}
      {(!options.supported || !options.candidates.length) && <p className="field-help"><b>连接提案暂不可提交</b></p>}
      {!!options.blockers.length && <div className="connection-blockers">{options.blockers.map((b, i) => <p key={i}>{b}</p>)}</div>}
    </>}
    {!options && <p className="field-help">先登记明确的输入与模式。候选检查保持静态；连接预览才执行隔离验证，所有必需门通过后才能审核提交。</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
  </section>;
}

export function bindingLabel(architecture: Architecture, document: CanvasDocument, binding: Binding) {
  const node = architecture.nodes.find(n => n.id === binding.nodeId);
  return document.displayAliases[binding.nodeId] ?? node?.label ?? binding.nodeId;
}
