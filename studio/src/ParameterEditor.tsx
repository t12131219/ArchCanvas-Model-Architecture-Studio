import { useEffect, useState } from 'react';
import type { ArchitectureNode } from './core';

export function ParameterEditor({ node, busy, enabled, onPrepare }: { node: ArchitectureNode; busy: boolean; enabled: boolean; onPrepare: (parameter: string, value: number) => void }) {
  const parameter = node.kind === 'Dropout' ? 'p' : node.kind === 'MultiheadAttention' ? 'dropout' : undefined;
  const origin = parameter ? node.parameterOrigins?.[parameter] : undefined;
  const value = parameter ? node.parameters[parameter] : undefined;
  const [draft, setDraft] = useState(String(value ?? ''));
  useEffect(() => setDraft(String(value ?? '')), [node.id, value]);
  if (!parameter) return null;
  const editable = enabled && origin?.kind === 'literal' && /[.eE]/.test(origin.expression) && typeof value === 'number';
  const numeric = Number(draft);
  return <section className="property-section semantic-editor"><h3>参数修改<span className="review-tag">先审核</span></h3>
    <label className="field-label" htmlFor="probability">{parameter} · 当前 {String(value)}</label>
    <div className="probability-input"><input id="probability" aria-label="新的 Dropout 概率" type="number" min="0" max="1" step="0.05" value={draft} disabled={!editable || busy} onChange={e => setDraft(e.target.value)} /><button onClick={() => onPrepare(parameter, numeric)} disabled={!editable || busy || !draft.trim() || !Number.isFinite(numeric) || numeric < 0 || numeric > 1 || numeric === value}>预览修改</button></div>
    {origin && <p className="field-help">来源：{origin.path}:{origin.line}<br /><code>{origin.expression}</code> · {origin.kind === 'literal' ? '源码字面量' : origin.kind === 'constructor_argument' ? '构造参数' : '派生或未知表达式'}</p>}
    <p className="field-help">{editable ? '修改 Studio 工作副本。预览会列出共享这一来源的全部调用；审核通过后才能提交。' : '本阶段仅支持明确浮点字面量；整数、构造参数、配置和派生表达式暂不支持写回。'}</p>
  </section>;
}
