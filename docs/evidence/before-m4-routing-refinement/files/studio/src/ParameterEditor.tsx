import { useEffect, useState } from 'react';
import type { ArchitectureNode } from './core';
import type { ConfigurationOptions } from './api';

export function ParameterEditor({ node, busy, enabled, onPrepare, onInspectConfiguration }: { node: ArchitectureNode; busy: boolean; enabled: boolean; onPrepare: (parameter: string, value: number, configuration: boolean) => void; onInspectConfiguration: (parameter: string) => Promise<ConfigurationOptions> }) {
  const parameter = node.kind === 'Dropout' ? 'p' : node.kind === 'MultiheadAttention' ? 'dropout' : undefined;
  const origin = parameter ? node.parameterOrigins?.[parameter] : undefined;
  const value = parameter ? node.parameters[parameter] : undefined;
  const [draft, setDraft] = useState(String(value ?? ''));
  const [configuration, setConfiguration] = useState<ConfigurationOptions | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { setDraft(String(value ?? '')); setConfiguration(null); setError(''); }, [node.id, value]);
  if (!parameter) return null;
  const literal = origin?.kind === 'literal' && /[.eE]/.test(origin.expression);
  const editable = enabled && (literal || configuration?.supported) && typeof value === 'number';
  const numeric = Number(draft);
  return <section className="property-section semantic-editor"><h3>参数修改<span className="review-tag">先审核</span></h3>
    <label className="field-label" htmlFor="probability">{parameter} · 当前 {String(value)}</label>
    <div className="probability-input"><input id="probability" aria-label="新的 Dropout 概率" type="number" min="0" max="1" step="0.05" value={draft} disabled={!editable || busy} onChange={e => setDraft(e.target.value)} /><button onClick={() => onPrepare(parameter, numeric, !literal)} disabled={!editable || busy || !draft.trim() || !Number.isFinite(numeric) || numeric < 0 || numeric > 1 || numeric === value}>预览修改</button></div>
    {origin && <p className="field-help">来源：{origin.path}:{origin.line}<br /><code>{origin.expression}</code> · {origin.kind === 'literal' ? '源码字面量' : origin.kind === 'constructor_argument' ? '构造参数' : '派生或未知表达式'}</p>}
    {!literal && <button disabled={!enabled || busy} onClick={async () => { setError(''); try { setConfiguration(await onInspectConfiguration(parameter)); } catch (e) { setError(String(e)); } }}>检查配置来源与影响</button>}
    {configuration?.target && <p className="field-help">配置：<code>{configuration.target.name}</code> · {configuration.target.origin.path}:{configuration.target.origin.line}<br />共 {configuration.affectedNodeIds.length} 个调用受影响；修改唯一配置值，保留读取表达式。</p>}
    {configuration?.blockers.map((blocker, i) => <p className="field-help" key={i}>{blocker}</p>)}
    {error && <p role="alert" className="error-text">{error}</p>}
    <p className="field-help">{editable ? '修改 Studio 工作副本。预览会列出共享这一来源的全部调用；审核通过后才能提交。' : '支持浮点字面量及唯一模块常量，配置的全部读取须为已注册概率参数。派生表达式和未证明影响范围保留为提案。'}</p>
  </section>;
}
