import { useEffect, useRef, useState } from 'react';
import { t } from './i18n';
import './SourceCodeWindow.css';

/** Monaco is loaded only when a source tool is opened; the canvas never pays its startup cost. */
export function PythonCodeEditor({ value, onChange, readOnly = false }: { value: string; onChange: (value: string) => void; readOnly?: boolean }) {
  const host = useRef<HTMLDivElement>(null), editor = useRef<import('monaco-editor').editor.IStandaloneCodeEditor | null>(null);
  const change = useRef(onChange), latest = useRef(value), options = useRef({ indent: 4, wrap: false, readOnly });
  change.current = onChange; latest.current = value; options.current.readOnly = readOnly;
  const [failure, setFailure] = useState(''), [indent, setIndent] = useState(4), [wrap, setWrap] = useState(false);
  useEffect(() => {
    let disposed = false;
    void Promise.all([
      import('./monacoPython'),
      import('monaco-editor/editor/editor.worker.js?worker'),
    ]).then(([monaco, worker]) => {
      if (disposed || !host.current) return;
      (globalThis as typeof globalThis & { MonacoEnvironment?: unknown }).MonacoEnvironment = { getWorker: () => new worker.default() };
      const instance = monaco.editor.create(host.current, { value: latest.current, language: 'python', theme: 'vs',
        automaticLayout: true, editContext: false, minimap: { enabled: false }, fontSize: 14, lineHeight: 23, padding: { top: 12 },
        scrollBeyondLastLine: false, tabSize: options.current.indent, wordWrap: options.current.wrap ? 'on' : 'off', insertSpaces: true, autoIndent: 'full', bracketPairColorization: { enabled: true },
        renderWhitespace: 'selection', readOnly: options.current.readOnly, fixedOverflowWidgets: true, ariaLabel: t('Python 源码编辑器') });
      editor.current = instance;
      instance.onDidChangeModelContent(() => change.current(instance.getValue()));
    }).catch(error => { if (!disposed) setFailure(String(error)); });
    return () => { disposed = true; const model = editor.current?.getModel(); editor.current?.dispose(); model?.dispose(); editor.current = null; };
  }, []);
  useEffect(() => { if (editor.current && editor.current.getValue() !== value) editor.current.setValue(value); }, [value]);
  useEffect(() => { editor.current?.updateOptions({ readOnly }); }, [readOnly]);
  function indentation(size: number) { options.current.indent = size; setIndent(size); editor.current?.getModel()?.updateOptions({ tabSize: size, insertSpaces: true }); }
  function normalizeIndent() {
    const instance = editor.current, model = instance?.getModel(); if (!instance || !model) return;
    // Monaco's built-in command preserves undo history and the selected block.
    void instance.getAction('editor.action.indentationToSpaces')?.run();
  }
  return <div className="python-code-editor"><div className="python-editor-tools"><span>Python</span><label>{t('缩进')} <select aria-label={t('缩进空格数')} value={indent} onChange={e => indentation(Number(e.target.value))}><option value={2}>2</option><option value={4}>4</option><option value={8}>8</option></select></label><button type="button" disabled={readOnly} onClick={normalizeIndent}>{t('Tab 转为空格')}</button><button type="button" aria-pressed={wrap} onClick={() => { options.current.wrap = !wrap; setWrap(!wrap); editor.current?.updateOptions({ wordWrap: wrap ? 'off' : 'on' }); }}>{t('自动换行')}</button><span className="python-editor-hint">Tab / Shift+Tab · Ctrl+F · Ctrl+Z</span></div><div className="python-editor-host" ref={host} />{failure && <p role="alert">{t('代码编辑器加载失败')}: {failure}</p>}</div>;
}
