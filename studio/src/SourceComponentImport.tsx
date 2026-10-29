import { t, uiMessage } from './i18n';
import { useState } from 'react';
import { api } from './api';

export function SourceComponentImport({ disabled, onSaved }: { disabled: boolean; onSaved: () => void }) {
  const [files, setFiles] = useState<Record<string, string>>({}), [entries, setEntries] = useState<string[]>([]);
  const [entry, setEntry] = useState(''), [title, setTitle] = useState(''), [config, setConfig] = useState('{}');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [status, setStatus] = useState('');
  async function read(selected: FileList | null, folder: boolean) {
    if (!selected?.length) return;
    setBusy(true); setError(''); setStatus(''); setFiles({}); setEntries([]); setEntry('');
    try {
      const accepted = Array.from(selected).filter(f => f.name.endsWith('.py') && !f.webkitRelativePath.split('/').some(p => ['.git', '.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build'].includes(p)));
      if (!accepted.length || accepted.length > 80 || accepted.reduce((n, f) => n + f.size, 0) > 2_000_000) throw Error('请选择 1–80 个 Python 文件，总计不超过 2 MB；大型项目可仅选择模型及其依赖目录。');
      const corpus: Record<string, string> = {};
      for (const file of accepted) {
        const path = folder ? file.webkitRelativePath.split('/').slice(1).join('/') : file.name;
        if (!path || Object.hasOwn(corpus, path)) throw Error(`源码路径重复：${path}`);
        corpus[path] = await file.text();
      }
      const inventory = await api.discoverComponentModels(corpus);
      if (inventory.syntaxErrors.length) throw Error(inventory.syntaxErrors.map(e => `${e.file}: ${e.message}`).join('\n'));
      if (!inventory.candidates.length) throw Error('没有发现可解析的模型入口，请包含定义模型和本地依赖的 Python 文件。');
      setFiles(corpus); setEntries(inventory.candidates); setEntry(inventory.candidates[0]);
      setTitle(folder ? accepted[0].webkitRelativePath.split('/')[0] : accepted[0].name.replace(/\.py$/, ''));
      setStatus(`已读取 ${accepted.length} 个文件；请选择需要提取的模型入口。`);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError(''); setStatus('正在静态解析并保存构件…');
    try {
      const parsed: unknown = JSON.parse(config);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw Error('构造参数需为 JSON 对象。');
      const result = await api.importSourceComponents({ files, entry, title, config: parsed as Record<string, unknown> });
      setStatus(`已保存到项目构件库：新增 ${result.added} 个版本，复用 ${result.reused} 个版本（共 ${result.candidates} 个源码实例）。`);
      onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setStatus(''); }
    finally { setBusy(false); }
  }
  return <details className="source-component-import"><summary>{t("从模型项目导入构件")}</summary>
    <p className="field-help">{t("读取 Python 源码并提取选定入口的模块和算子，保存到独立的项目构件库。重复版本自动合并，刷新后仍可复用。")}</p>
    <label className="field-label">{t("选择项目目录")}<input aria-label={t("构件库项目目录")} type="file" multiple {...{ webkitdirectory: '' }} disabled={disabled || busy} onChange={e => { void read(e.target.files, true); e.target.value = ''; }} /></label>
    <label className="field-label">{t("或选择 Python 文件")}<input aria-label={t("构件库 Python 文件")} type="file" accept=".py" multiple disabled={disabled || busy} onChange={e => { void read(e.target.files, false); e.target.value = ''; }} /></label>
    {entries.length > 0 && <>
      <label className="field-label">{t("项目名称")}<input aria-label={t("构件来源项目名称")} value={title} maxLength={160} disabled={disabled || busy} onChange={e => setTitle(e.target.value)} /></label>
      <label className="field-label">{t("模型入口")}<select aria-label={t("构件提取模型入口")} value={entry} disabled={disabled || busy} onChange={e => setEntry(e.target.value)}>{entries.map(v => <option key={v}>{v}</option>)}</select></label>
      <label className="field-label">{t("构造参数（JSON）")}<textarea aria-label={t("构件提取构造参数")} rows={3} value={config} disabled={disabled || busy} onChange={e => setConfig(e.target.value)} /></label>
      <p className="field-help">{t("每次提取限 480 节点 / 3600 依赖；可选择子模块入口分批提取。")}</p>
      <button className="full-button" disabled={disabled || busy || !title.trim()} onClick={() => void save()}>{t("解析并保存构件")}</button>
    </>}
    {status && <p className="field-help" role="status">{status}</p>}{error && <p role="alert">{uiMessage(error)}</p>}
  </details>;
}
