import { useRef, useState } from 'react';
import { api } from './api';
import { Icon } from './icons';
import type { CustomModulePreview } from './customModules';
import { readCustomModuleDefinition } from './customModules';

const EXAMPLE = `from torch import nn

class CustomBlock(nn.Module):
    def __init__(self, width=16):
        super().__init__()
        self.project = nn.Linear(width, width)
        self.activation = nn.Tanh()

    def forward(self, x):
        return self.activation(self.project(x))
`;
export function CustomModuleDialog({ onClose, onInsert }: { onClose: () => void; onInsert: (preview: CustomModulePreview) => void }) {
  const [source, setSource] = useState(EXAMPLE), [entry, setEntry] = useState('CustomBlock'), [label, setLabel] = useState('我的源码模块');
  const [constructorText, setConstructorText] = useState('{"width": 16}');
  const [preview, setPreview] = useState<CustomModulePreview | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const inFlight = useRef(false);
  function change(update: () => void) { update(); setPreview(null); setError(''); }
  async function inspect() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(''); setPreview(null);
    try {
      const constructorValues = JSON.parse(constructorText);
      if (!constructorValues || typeof constructorValues !== 'object' || Array.isArray(constructorValues)) throw new Error('构造参数应为 JSON 对象，如 {"width":16}');
      const result = await api.previewCustomModule({ source, entry, label, constructorValues });
      readCustomModuleDefinition(result.definition); setPreview(result);
    } catch (reason) { setError(String(reason)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <div className="modal-backdrop"><section className="custom-source-modal" role="dialog" aria-modal="true" aria-labelledby="custom-source-title">
    <div className="modal-heading"><div><span className="eyebrow">CUSTOM SOURCE MODULE</span><h2 id="custom-source-title">用源码创建模块</h2></div><button disabled={busy} aria-label="关闭源码模块窗口" onClick={onClose}><Icon name="close" /></button></div>
    <p>编写一个 nn.Module 类，静态预览后加入当前模型。模块可以重复拖入，源码和构造参数随草稿保存。</p>
    <div className="custom-module-fields"><label>类名<input aria-label="自定义模块类名" disabled={busy} value={entry} onChange={event => change(() => setEntry(event.target.value))} /></label><label>显示名称<input aria-label="自定义模块显示名称" disabled={busy} value={label} onChange={event => change(() => setLabel(event.target.value))} /></label></div>
    <textarea aria-label="自定义模块 Python 源码" className="custom-source-editor" spellCheck={false} disabled={busy} value={source} onChange={event => change(() => setSource(event.target.value))} />
    <label className="custom-source-label">构造参数（JSON 对象）<textarea aria-label="自定义模块构造参数" className="custom-constructor" spellCheck={false} disabled={busy} value={constructorText} onChange={event => change(() => setConstructorText(event.target.value))} /></label>
    {error && <p className="error-text" role="alert">{error}</p>}
    {preview && <div className="custom-contract" role="status"><b>{preview.module.label} · {preview.definition.entry}</b><div className="custom-port-list">{preview.module.ports.map(port => <code key={port.id}>{port.direction === 'in' ? '输入' : '输出'} {port.name}</code>)}</div><p>仅解析源码，未执行模型；输出形状保留为未知。多输出将按静态返回路径连接。</p>{preview.architecture.diagnostics.filter(item => item.level !== 'info').map((item, index) => <p key={index}>{item.message}</p>)}<details><summary>静态结构 · {preview.architecture.nodes.length} 个事实对象</summary><pre>{preview.architecture.nodes.map(node => `${node.label} · ${node.kind} · ${node.evidence}`).join('\n')}</pre></details></div>}
    <div className="modal-actions"><button disabled={busy} onClick={onClose}>取消</button><button disabled={busy || !source.trim() || !entry.trim()} onClick={() => void inspect()}>{busy ? '正在静态预览…' : '静态预览'}</button><button className="primary" disabled={busy || !preview} onClick={() => { if (preview) onInsert(preview); }}>添加到模型</button></div>
  </section></div>;
}
