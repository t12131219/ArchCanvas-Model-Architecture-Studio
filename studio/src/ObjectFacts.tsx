import { t } from './i18n';
import type { Architecture, ArchitectureNode } from './core/types';
import { evidenceText, instanceCalls, outputPathText } from './core/nodeFacts';
import './ObjectFacts.css';

export function ObjectFacts({ architecture, node, onSelect }: {
  architecture: Architecture; node: ArchitectureNode; onSelect?: (id: string) => void;
}) {
  const calls = instanceCalls(architecture, node);
  return <section className="property-section object-facts" aria-label={t("对象来源事实")}>
    <h3>{t("对象来源")}<span className="read-only">{t("只读")}</span></h3>
    {node.repeat && <p className="field-help" data-fact="repeat">{node.repeat.count}{t("次重复 ·")}{node.repeat.sharing === 'shared' ? t("共享实例") : t("独立实例")}</p>}
    {calls.length > 1 && <>
      <p className="field-help" data-fact="shared-instance">{t("共享同一实例 ·")}{calls.length}{t("个不同调用")}</p>
      <ul className="fact-peer-list">{calls.map((call, index) => <li key={call.id}>{onSelect && call.id !== node.id
        ? <button className="text-button" onClick={() => onSelect(call.id)}>{call.label}{t("· 调用")}{index + 1}</button>
        : <span>{call.label}{t("· 调用")}{index + 1}{call.id === node.id ? t("（当前）") : ''}</span>}</li>)}</ul>
    </>}
    {node.outputPath && <p className="field-help" data-fact="output-path">{t("返回槽位：")}<code>{outputPathText(node.outputPath)}</code></p>}
    <p className="field-help" data-fact="evidence">{evidenceText(node)}</p>
    {node.source && <p className="field-help" data-fact="source">{node.source.path}:{node.source.line}–{node.source.endLine}</p>}
    <details className="fact-identities"><summary>{t("稳定身份与原始表达式")}</summary><dl className="parameters">
      <div><dt>{t("对象")}</dt><dd>{node.id}</dd></div>
      {node.instanceId && <div><dt>{t("实例")}</dt><dd>{node.instanceId}</dd></div>}
      {node.callId && <div><dt>{t("调用")}</dt><dd>{node.callId}</dd></div>}
      {node.source && <div><dt>{t("表达式")}</dt><dd>{node.source.expression}</dd></div>}
    </dl></details>
  </section>;
}
