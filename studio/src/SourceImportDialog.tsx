import { t, uiMessage } from './i18n';
import { useRef, useState } from 'react';
import { Icon } from './icons';
import { useModalFocus } from './WorkspaceUI';

type Props = {
  entry: string; filename: string; source: string; busy: boolean; error: string;
  onEntry: (value: string) => void; onFilename: (value: string) => void; onSource: (value: string) => void;
  onJson: (text: string) => Promise<void>; onError: (message: string) => void;
  onAnalyze: () => void; onProject: () => void; onClose: () => void;
};
export function SourceImportDialog(props: Props) {
  const panel = useModalFocus<HTMLDivElement>(props.onClose);
  const file = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<'code' | 'project'>('code');
  const [loaded, setLoaded] = useState('');
  return <div className="modal-backdrop"><div ref={panel} className="import-modal source-import" role="dialog" aria-modal="true" aria-labelledby="import-title">
    <div className="modal-heading"><div><h2 id="import-title">{t("打开模型")}</h2><p>{t("从源码建立模型视图，或恢复已保存的文档。")}</p></div><button className="tool" onClick={props.onClose} aria-label={t("关闭导入")}><Icon name="close" /></button></div>
    <div className="import-tabs" role="tablist" aria-label={t("导入方式")}><button role="tab" id="import-code-tab" aria-controls="import-code" aria-selected={tab === 'code'} onClick={() => setTab('code')}>{t("Python 单文件")}</button><button role="tab" id="import-project-tab" aria-controls="import-project" aria-selected={tab === 'project'} onClick={() => setTab('project')}>{t("工程目录 / 已有文档")}</button></div>
      <input ref={file} hidden type="file" accept=".py,.json" aria-label={t("选择源文件")} onChange={async event => {
        const chosen = event.target.files?.[0]; if (!chosen) return;
        try { const json = chosen.name.toLowerCase().endsWith('.json'); if (chosen.size > (json ? 128_000_000 : 2_000_000)) throw new Error(json ? t("编辑 JSON 超过 128 MB") : t("Python 源码超过 2 MB"));
          const text = await chosen.text(); if (json) await props.onJson(text); else { props.onSource(text); props.onFilename(chosen.name); setLoaded(chosen.name); setTab('code'); props.onError(''); }
        } catch (error) { props.onError(t("导入失败：{0}", {"0": String(error)})); } event.target.value = '';
      }} />
    {tab === 'code' ? <section role="tabpanel" id="import-code" aria-labelledby="import-code-tab">
      <div className="import-file-row"><button onClick={() => file.current?.click()}><Icon name="file" size={15} />{t("选择 .py 文件")}</button><span role="status">{loaded || t("也可以在下方粘贴源码")}</span></div>

      <div className="import-fields"><label>{t("模型入口")}<input aria-label={t("模型入口类名")} value={props.entry} placeholder={t("例如 Model")} onChange={event => props.onEntry(event.target.value)} /><small>{t("源码中的 nn.Module 类名")}</small></label><label>{t("源文件名")}<input aria-label={t("源文件名")} value={props.filename} placeholder="model.py" onChange={event => props.onFilename(event.target.value)} /><small>{t("用于保存源码位置")}</small></label></div>
      <label className="import-code-label" htmlFor="import-source-code">{t("Python 源码")}<span>{t("静态分析 · 不执行模型")}</span></label><textarea id="import-source-code" aria-label={t("Python 源码")} spellCheck={false} placeholder={'import torch\nfrom torch import nn\n\nclass Model(nn.Module):\n    ...'} value={props.source} onChange={event => props.onSource(event.target.value)} />
    </section> : <section role="tabpanel" id="import-project" aria-labelledby="import-project-tab" className="import-project-options"><Icon name="layers" size={28} /><h3>{t("打开完整工程或恢复文档")}</h3><p>{t("选择多个 Python 文件或源码目录，扫描模型与包含层级后选择入口。也可载入 Summary 原生文档、语义画布、架构文档、authoring 文档、IR、编辑 JSON 或源码适配包。")}</p><button onClick={() => file.current?.click()}><Icon name="file" size={16} />{t("选择 Summary / 编辑 JSON")}</button><button onClick={props.onProject}><Icon name="file" size={16} />{t("选择源码目录或多个文件")}</button><small>{t("源码：最多 80 个文件 / 2 MB · 文档 JSON：128 MB")}</small></section>}
    {props.error && <p className="import-error" role="alert">{uiMessage(props.error)}</p>}
    <div className="modal-actions"><span>{props.busy ? t("正在静态分析…") : t("原始源码保持不变")}</span><button onClick={props.onClose}>{t("取消")}</button>{tab === 'code' && <button className="primary" onClick={props.onAnalyze} disabled={props.busy || !props.source.trim() || !props.entry.trim() || !props.filename.trim()}>{props.busy ? t("分析中…") : t("分析并打开")}</button>}</div>
  </div></div>;
}
