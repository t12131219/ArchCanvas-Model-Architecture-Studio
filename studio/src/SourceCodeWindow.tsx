import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api } from './api';
import { t, uiMessage } from './i18n';
import { PythonCodeEditor } from './PythonCodeEditor';
import './SourceCodeWindow.css';

export type SourceCandidate = { entry: string; line: number; root: boolean; suggestedMode: 'model' | 'module'; dependencies: string[]; constructor: Record<string, unknown>; required: string[]; reason: string };
export type SourceInventory = { candidates: SourceCandidate[]; recommended: string | null; diagnostics: { message: string; line: number; column: number }[]; executed: false };
export function SourceCodeWindow({ source, entry, config, onSource, onEntry, onConfig, onClose, onApply, busy, canReplace }: {
  source: string; entry: string; config: string; onSource: (value: string) => void; onEntry: (value: string) => void; onConfig: (value: string) => void;
  onClose: () => void; onApply: (mode: 'module' | 'model' | 'replace') => Promise<void>; busy: boolean; canReplace: boolean;
}) {
  const panel = useRef<HTMLElement>(null), ticket = useRef(0), mounted = useRef(true), latestSource = useRef(source);
  latestSource.current = source;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; ++ticket.current; }; }, []);
  useEffect(() => {
    const element = panel.current; if (!element) return;
    const clamp = () => { const rect = element.getBoundingClientRect();
      element.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8)) + 'px';
      element.style.top = Math.max(8, Math.min(rect.top, window.innerHeight - rect.height - 8)) + 'px';
    };
    const observer = new ResizeObserver(clamp); observer.observe(element); window.addEventListener('resize', clamp);
    return () => { observer.disconnect(); window.removeEventListener('resize', clamp); };
  }, []);
  const [inventory, setInventory] = useState<SourceInventory | null>(null), [inspecting, setInspecting] = useState(false), [error, setError] = useState('');
  const [mode, setMode] = useState<'module' | 'model'>('module');
  const [scanned, setScanned] = useState('');
  const validInventory = scanned === source ? inventory : null;
  async function inspect() {
    const request = ++ticket.current; setInspecting(true); setError('');
    try {
      const result = await api.inspectSummarySource(source);
      if (!mounted.current || request !== ticket.current || latestSource.current !== source) return;
      setInventory(result); setScanned(source);
      if (result.diagnostics.length) setError(result.diagnostics.map(d => `${d.line}:${d.column} ${d.message}`).join('\n'));
      if (result.recommended) select(result.recommended, result);
      else if (result.candidates.length && !result.candidates.some(c => c.entry === entry)) onEntry('');
      else if (!result.candidates.length && !result.diagnostics.length) setError(t('没有找到 nn.Module 入口，请检查继承关系。'));
    } catch (e) { if (mounted.current && request === ticket.current) setError(String(e)); }
    finally { if (mounted.current && request === ticket.current) setInspecting(false); }
  }
  function select(name: string, result = inventory) {
    onEntry(name);
    const candidate = result?.candidates.find(c => c.entry === name);
    if (candidate) {
      setMode(candidate.suggestedMode);
      let constructor = candidate.constructor;
      if (name === entry) { try { const current = JSON.parse(config); if (!current || typeof current !== 'object' || Array.isArray(current)) return; constructor = { ...constructor, ...current }; } catch { return; } }
      onConfig(JSON.stringify(constructor, null, 2));
    }
  }
  const candidate = validInventory?.candidates.find(c => c.entry === entry);
  const locked = busy || inspecting;
  function close() { ++ticket.current; onClose(); }
  return createPortal(<section ref={panel} className="source-code-window" role="dialog" aria-label={t('Python 源码工作台')} onKeyDown={e => { e.stopPropagation(); if (!e.defaultPrevented && e.key === 'Escape' && !locked) { e.stopPropagation(); close(); } }}>
    <header className="source-code-window-header" onPointerDown={e => {
      if (e.button !== 0 || (e.target as HTMLElement).closest('button')) return;
      const target = e.currentTarget, rect = panel.current!.getBoundingClientRect(), x = e.clientX, y = e.clientY;
      target.setPointerCapture(e.pointerId);
      const move = (ev: PointerEvent) => { if (!panel.current) return; panel.current.style.left = Math.max(8, Math.min(window.innerWidth - rect.width - 8, rect.left + ev.clientX - x)) + 'px'; panel.current.style.top = Math.max(8, Math.min(window.innerHeight - rect.height - 8, rect.top + ev.clientY - y)) + 'px'; };
      const end = () => { target.removeEventListener('pointermove', move); target.removeEventListener('pointerup', end); target.removeEventListener('pointercancel', end); };
      target.addEventListener('pointermove', move); target.addEventListener('pointerup', end); target.addEventListener('pointercancel', end);
    }}><h2>{t('Python 源码工作台')}</h2><button aria-label={t('关闭源码窗口')} disabled={locked} onClick={close}>×</button></header>
    <div className="source-code-window-body"><p className="source-code-note">{t('可拖动标题栏、调整窗口大小。支持整模型或单模块；源码仅静态解析。')}</p>
      <div className="source-code-actions"><button disabled={locked || !source.trim()} onClick={() => void inspect()}>{inspecting ? t('正在识别…') : t('识别入口与模型结构')}</button>{validInventory && <span className="source-code-note">{t('找到 {0} 个入口', {0: validInventory.candidates.length})}</span>}</div>
      <div className="source-code-fields"><label>{t('模块入口')}{validInventory?.candidates.length ? <select aria-label={t('识别出的源码入口')} value={entry} disabled={locked} onChange={e => select(e.target.value)}><option value="">{t('请选择入口')}</option>{validInventory.candidates.map(c => <option key={c.entry} value={c.entry}>{c.entry} · L{c.line}{c.root ? ' · root' : ''}</option>)}</select> : <input aria-label={t('源码窗口入口')} disabled={locked} value={entry} onChange={e => onEntry(e.target.value)} />}</label><label>{t('导入方式')}<select aria-label={t('源码导入方式')} value={mode} disabled={locked} onChange={e => setMode(e.target.value as 'module' | 'model')}><option value="module">{t('作为构件加入当前模型')}</option><option value="model">{t('作为完整模型打开新副本')}</option></select></label></div>
      {candidate && <p className="source-code-note">{candidate.reason === 'composition-root' ? t('该入口组合了子模块，推荐作为完整模型；也可作为可复用构件。') : t('该入口可作为独立构件；也可作为完整模型打开。')}{candidate.required.length > 0 && <> {t('需要填写构造参数：{0}', {0: candidate.required.join(', ')})}</>}</p>}
      <PythonCodeEditor value={source} onChange={value => { ++ticket.current; setInspecting(false); onSource(value); setError(''); }} readOnly={busy} />
      <label className="field-label">{t('构造参数（JSON 对象）')}<textarea aria-label={t('源码窗口构造参数')} rows={2} value={config} disabled={locked} onChange={e => onConfig(e.target.value)} /></label>
      {error && <p role="alert">{uiMessage(error)}</p>}
      <footer className="source-code-actions"><button className="primary" disabled={locked || !source.trim() || !entry.trim()} onClick={() => void onApply(mode).catch(e => setError(String(e)))}>{busy ? t('正在解析…') : mode === 'model' ? t('解析并打开完整模型') : t('解析并加入源码模块')}</button><button disabled={locked || !canReplace} onClick={() => void onApply('replace').catch(e => setError(String(e)))}>{t('重新解析并替换选中构件')}</button><span className="source-code-note">{t('关闭后保留输入内容。')}</span></footer>
    </div>
  </section>, document.body);
}
