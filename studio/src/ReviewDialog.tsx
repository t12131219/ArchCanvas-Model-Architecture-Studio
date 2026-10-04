import { useMemo, useState } from 'react';
import { applyVisualBatch, buildScene, reconcileDocument, renderSvg } from './core';
import type { CanvasDocument } from './core';
import type { Transaction } from './api';
import { Icon } from './icons';
import { bindingLabel } from './ConnectionEditor';

function figure(base: CanvasDocument, transaction: Transaction, after: boolean, focus: boolean) {
  const architecture = after ? transaction.afterArchitecture : transaction.beforeArchitecture;
  if (!architecture) return '';
  let doc = reconcileDocument(base, architecture).document;
  for (const id of transaction.affectedNodeIds) {
    let node = architecture.nodes.find(n => n.id === id);
    while (node?.parentId) {
      const parent = architecture.nodes.find(n => n.id === node!.parentId)!;
      if (!doc.expandedIds.includes(parent.id)) doc = applyVisualBatch(doc, [{ type: 'expand', id: parent.id, expanded: true }]);
      node = parent;
    }
    if (architecture.nodes.some(n => n.id === id)) doc = applyVisualBatch(doc, [{ type: 'nodeStyle', id, style: { stroke: '#bd7533' } }]);
  }
  if (transaction.intent.kind === 'RebindInput') {
    const intent = transaction.intent;
    for (const edge of architecture.edges.filter(e => e.target.nodeId === intent.nodeId && e.target.portId === intent.portId)) {
      doc = applyVisualBatch(doc, [{ type: 'edgeStyle', id: edge.id, style: { stroke: '#bd7533', width: 2.8 } }]);
    }
  }
  const scene = buildScene(doc);
  let svg = renderSvg(scene);
  if (focus) {
    const affected = new Set(transaction.affectedNodeIds);
    const context = new Set(affected);
    for (const edge of architecture.edges) if (affected.has(edge.source.nodeId) || affected.has(edge.target.nodeId)) { context.add(edge.source.nodeId); context.add(edge.target.nodeId); }
    const nodes = scene.nodes.filter(n => context.has(n.id) && !n.expanded);
    if (nodes.length) {
      const x = Math.min(...nodes.map(n => n.x)) - 20, y = Math.min(...nodes.map(n => n.y)) - 20;
      const width = Math.max(...nodes.map(n => n.x + n.width)) - x + 20;
      const height = Math.max(...nodes.map(n => n.y + n.height)) - y + 20;
      svg = svg.replace(/viewBox="[^"]*"/, `viewBox="${x} ${y} ${width} ${height}"`);
    }
  }
  return svg;
}
const statuses: Record<string, string> = { ReviewReady: '待审核', Approved: '已批准 · 待提交', Committed: '已提交', Failed: '准备失败', Stale: '版本已过期', RolledBack: '已恢复原版本', ManualRecovery: '需要手动恢复', Discarded: '已取消' };
export function ReviewDialog({ base, transaction, busy, error, onApprove, onCommit, onClose }: { base: CanvasDocument; transaction: Transaction; busy: boolean; error: string; onApprove: () => void; onCommit: () => void; onClose: () => void }) {
  const [checked, setChecked] = useState(false);
  const [focus, setFocus] = useState(true);
  const before = useMemo(() => figure(base, transaction, false, focus), [base, transaction, focus]);
  const after = useMemo(() => figure(base, transaction, true, focus), [base, transaction, focus]);
  const intent = transaction.intent;
  const rebind = intent.kind === 'RebindInput';
  const beforeValue = rebind ? intent.before?.variable ?? '未解析' : String(intent.before ?? '—');
  const afterValue = rebind ? intent.after?.variable ?? '未解析' : String(intent.after);
  const target = base.displayAliases[intent.nodeId] ?? transaction.beforeArchitecture?.nodes.find(n => n.id === intent.nodeId)?.label ?? intent.nodeId;
  const portName = rebind ? base.architecture.nodes.find(n => n.id === intent.nodeId)?.ports.find(p => p.id === intent.portId)?.name ?? '输入' : '';
  return <div className="modal-backdrop"><div className="review-modal" role="dialog" aria-modal="true" aria-labelledby="review-title">
    <div className="modal-heading"><div><div className="eyebrow">SOURCE CHANGE REVIEW</div><h2 id="review-title">{rebind ? '审核连接修改' : '审核参数修改'}</h2></div><button className="tool" onClick={onClose} disabled={busy} aria-label="关闭审核"><Icon name="close" /></button></div>
    <div className="review-scope"><b>Studio 工作副本</b><span>{statuses[transaction.status] ?? transaction.status}</span><p>提交将修改本地工作副本中的源码。导入前的原始文件不在这次修改范围内。</p></div>
    <div className="change-summary"><strong>{rebind ? `${target} · 输入连接` : intent.parameter}</strong><span>{beforeValue} <b>→</b> {afterValue}</span><small>{transaction.affectedNodeIds.length} 个对象受影响</small></div>
    {rebind && <div className="rebind-summary"><span>目标端口：<code>{portName}</code></span><span>来源：{intent.before && bindingLabel(base.architecture, base, intent.before)} → {intent.after && bindingLabel(base.architecture, base, intent.after)}</span><p>改接会改变目标及下游的计算行为。符号兼容性以输入张量有效、注册算子保持形状与类型为条件；没有具体形状或运行时验证。</p></div>}
    {!!transaction.blockers.length && <div className="review-blockers">{transaction.blockers.map((b, i) => <p key={i}>{b}</p>)}</div>}
    {before && after && <><div className="review-view"><span>前后架构</span><button className={focus ? 'active' : ''} onClick={() => setFocus(true)}>影响区域</button><button className={!focus ? 'active' : ''} onClick={() => setFocus(false)}>完整架构</button></div><div className="review-figures"><figure><figcaption>修改前 · {beforeValue}</figcaption><div dangerouslySetInnerHTML={{ __html: before }} /></figure><figure><figcaption>修改后 · {afterValue}<span>{rebind ? '橙色为改接连线与影响对象' : '橙色边框为受影响节点'}</span></figcaption><div dangerouslySetInnerHTML={{ __html: after }} /></figure></div></>}
    <div className="review-columns"><section><h3>最小源码改动</h3><pre className="source-diff">{transaction.diff || '没有可提交的源码 diff。'}</pre><details><summary>受影响的对象与来源</summary><ul>{transaction.affectedNodeIds.map(id => <li key={id}>{transaction.beforeArchitecture?.nodes.find(n => n.id === id)?.label ?? id}<code>{id}</code></li>)}</ul>{transaction.intent.origin && <p>{transaction.intent.origin.path}:{transaction.intent.origin.line} · <code>{transaction.intent.origin.expression}</code></p>}</details></section>
    <section><h3>验证结果</h3><div className="review-gates">{transaction.gates.map(g => <details key={g.id}><summary><i className={g.status === 'passed' ? 'passed' : g.status === 'failed' ? 'failed' : 'pending'} /><span>{g.label}</span><small>{g.status === 'passed' ? '通过' : g.status === 'failed' ? '失败' : '未执行'}</small></summary><p>{g.message}</p></details>)}</div></section></div>
    <p className="review-note">模型未被执行；没有运行时或数值等价性验证。{transaction.checkpointImpact.message} 提交后保留能唯一对应的节点样式与位置；绑定改变的连线重新使用默认样式。</p>
    {rebind && intent.contract && <details className="review-binding"><summary>符号契约与条件</summary><p>{intent.contract.condition}</p><p>端口：<code>{intent.portId}</code></p><p>形状：<code>{intent.contract.shape.identity}</code> · 类型：<code>{intent.contract.dtype.identity}</code></p></details>}
    <details className="review-binding"><summary>查看版本绑定</summary><p>源码：<code>{transaction.sourceDigest}</code></p><p>审核：<code>{transaction.reviewDigest ?? '无'}</code></p></details>
    {error && <p className="error-text" role="alert">{error}</p>}
    <div className="review-actions">{transaction.status === 'ReviewReady' && <label><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} />我已核对改动、影响范围与验证结果</label>}<button onClick={onClose} disabled={busy}>{transaction.status === 'Committed' ? '完成' : '取消'}</button>{transaction.status === 'ReviewReady' && <button className="primary" disabled={!checked || busy} onClick={onApprove}>批准这份修改</button>}{transaction.status === 'Approved' && <button className="primary" disabled={busy} onClick={onCommit}>提交到工作副本</button>}</div>
  </div></div>;
}
