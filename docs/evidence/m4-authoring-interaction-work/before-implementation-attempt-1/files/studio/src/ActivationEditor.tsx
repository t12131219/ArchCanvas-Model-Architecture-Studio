import type { ArchitectureNode } from './core';
import type { InputSpec } from './api';

export function ActivationEditor({ node, enabled, busy, inputSpec, onSetup, onPrepare }: {
  node: ArchitectureNode; enabled: boolean; busy: boolean; inputSpec: InputSpec | null; onSetup: () => void; onPrepare: (activation: string) => void;
}) {
  if (!['ReLU', 'GELU'].includes(node.kind)) return null;
  const next = node.kind === 'ReLU' ? 'GELU' : 'ReLU';
  return <section className="property-section semantic-editor"><h3>激活函数<span className="review-tag">先审核</span></h3>
    <p className="field-help">当前 {node.kind} → {next}。仅支持直接、无参数的构造；替换会改变计算数值，保留调用连线与张量合同。</p>
    <button disabled={busy} onClick={onSetup}>{inputSpec ? '调整运行输入与模式' : '设置运行输入与模式'}</button>
    <button disabled={busy || !enabled || !inputSpec} onClick={() => onPrepare(next)}>运行验证并预览激活替换</button>
  </section>;
}
