import { useState } from 'react';
import type { Architecture } from './core';
import type { InputSpec } from './api';
import { Icon } from './icons';

export function RuntimeProfileDialog({ architecture, initial, example, onSave, onClose }: {
  architecture: Architecture; initial: InputSpec | null; example: boolean; onSave: (spec: InputSpec) => void; onClose: () => void;
}) {
  const names = architecture.nodes.filter(n => n.kind === 'Input').map(n => n.label);
  const demo = { query: { shape: [2, 3, 8], dtype: 'float32' }, memory: { shape: [2, 5, 8], dtype: 'float32' }, alternative: { shape: [2, 5, 8], dtype: 'float32' }, padding_mask: { shape: [2, 5], dtype: 'bool' } };
  const [draft, setDraft] = useState(JSON.stringify(initial?.inputs ?? (example ? demo : Object.fromEntries(names.map(name => [name, { shape: [], dtype: 'float32' }]))), null, 2));
  const [constructor, setConstructor] = useState(JSON.stringify(initial?.constructor ?? {}, null, 2));
  const [seed, setSeed] = useState(String(initial?.seed ?? 0));
  const [evalMode, setEval] = useState(initial?.modes.includes('eval') ?? true);
  const [trainMode, setTrain] = useState(initial?.modes.includes('train') ?? true);
  const [error, setError] = useState('');
  function save() {
    try {
      const inputs = JSON.parse(draft) as InputSpec['inputs'];
      if (!inputs || typeof inputs !== 'object' || Array.isArray(inputs) || Object.keys(inputs).sort().join('|') !== [...names].sort().join('|')) throw new Error('请为每个源码输入填写一份形状和类型，名称须完全一致。');
      for (const input of Object.values(inputs)) if (!Array.isArray(input.shape) || !input.shape.length || input.shape.some(d => !Number.isInteger(d) || d < 1) || typeof input.dtype !== 'string') throw new Error('shape 必须是正整数数组，dtype 必须明确填写。');
      const constructorValues = JSON.parse(constructor) as Record<string, unknown>;
      if (!constructorValues || typeof constructorValues !== 'object' || Array.isArray(constructorValues)) throw new Error('构造参数须为 JSON 对象。');
      if (Object.keys(constructorValues).length) throw new Error('当前验证合同仅支持源码中的默认构造参数，请保留 {}。');
      if (!Number.isSafeInteger(Number(seed)) || Number(seed) < 0 || !evalMode && !trainMode) throw new Error('填写非负整数随机种子，并至少选择一种运行模式。');
      onSave({ schemaVersion: 1, inputs, seed: Number(seed), modes: [...(evalMode ? ['eval' as const] : []), ...(trainMode ? ['train' as const] : [])], constructor: constructorValues });
    } catch (e) { setError(String(e)); }
  }
  return <div className="modal-backdrop"><div className="runtime-modal" role="dialog" aria-modal="true" aria-labelledby="runtime-title">
    <div className="modal-heading"><div><div className="eyebrow">ISOLATED CPU VALIDATION</div><h2 id="runtime-title">连接验证的输入与模式</h2></div><button className="tool" aria-label="关闭运行设置" onClick={onClose}><Icon name="close" /></button></div>
    <p className="runtime-intro">为 {architecture.label} 明确输入。预览语义修改时，将在隔离 CPU worker 中运行候选源码，核对从当前源码与修改意图独立推导的调用、形状、类型和状态预期。现在保存设置只登记输入，不执行模型。</p>
    {example && <p className="field-help">以下是这个示例的演示输入，可修改；它们不是自动推断的实际训练输入。</p>}
    <label className="field-label" htmlFor="runtime-inputs">具名输入 · {names.join('、')}</label>
    <textarea id="runtime-inputs" aria-label="运行输入 JSON" value={draft} onChange={e => setDraft(e.target.value)} spellCheck={false} />
    <div className="runtime-fields"><label>随机种子<input aria-label="运行随机种子" type="number" min="0" value={seed} onChange={e => setSeed(e.target.value)} /></label><label className="check-field"><input type="checkbox" checked={evalMode} onChange={e => setEval(e.target.checked)} />评估模式 eval</label><label className="check-field"><input type="checkbox" checked={trainMode} onChange={e => setTrain(e.target.checked)} />训练模式 train</label></div>
    <details><summary>模型构造参数</summary><p className="field-help">当前合同使用源码中的默认构造参数，须保留 {'{}'}；不加载 checkpoint。</p><textarea aria-label="模型构造参数 JSON" className="constructor-input" value={constructor} onChange={e => setConstructor(e.target.value)} spellCheck={false} /></details>
    <p className="review-note">默认禁网、只读源码、独立临时写入目录，并限制时间和资源。缺少已验证隔离环境或所需运行检查失败时，连接提案无法提交。样本检查不证明全程序或数值等价。</p>
    {error && <p role="alert" className="error-text">{error}</p>}
    <div className="modal-actions"><button onClick={onClose}>取消</button><button className="primary" onClick={save}>保存输入设置</button></div>
  </div></div>;
}
