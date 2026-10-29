import { t } from './i18n';
import type { PreviewEvidenceSource } from './previewInterop';

type Fact = Record<string, unknown>;
const record = (value: unknown): Fact => value && typeof value === 'object' && !Array.isArray(value) ? value as Fact : {};
const rows = (value: unknown): Fact[] => Array.isArray(value) ? value.map(record) : [];
const label = (value: unknown) => typeof value === 'string' ? value : '';
const evidenceLabels: Record<string, string> = { 'static-only': '静态源码', opaque: '未知边界', 'runtime-only': '运行观察',
  'source-runtime-associated': '源码与观察关联', 'static-runtime-consistent': '源码与观察一致', 'unobserved-branch': '未观察分支', conflict: '证据冲突' };

/** Read-only evidence projection. Graph/frontier/selection remain in Summary. */
export function SummarySemanticPanel({ source, selectedIds, onFocus, onEvidence, embedded = false }: {
  embedded?: boolean; source?: PreviewEvidenceSource; selectedIds: string[]; onFocus: (id: string) => void; onEvidence: () => void;
}) {
  if (source?.schema !== 'summary-source-adapter/1' || source.ir?.semanticSchema !== 'archcanvas-source-semantic/2') return null;
  const ir = record(source.ir.semantic_ir), nodes = rows(ir.nodes), byId = new Map(nodes.map(node => [label(node.id), node]));
  const selected = selectedIds.map(id => byId.get(id)).filter((node): node is Fact => !!node);
  const coverage = record(ir.coverage), runtime = record(ir.runtime), contracts = rows(ir.semantic_contracts), motifs = rows(ir.motifs);
  const opaque = nodes.filter(node => node.kind === 'opaque'), branches = rows(ir.branches), blockers = rows(ir.coverage_blockers);
  const focus = (id: unknown) => { if (typeof id === 'string' && byId.has(id)) onFocus(id); };
  return <details className={embedded ? "summary-semantic" : "inspector-section summary-semantic"}>
    <summary>{t("源码证据")}<span className="read-only">{t("只读证据")}</span></summary>
    <div className="coordinate-row"><label>{t("语义版本")}<output>v2</output></label><label>{t("模型执行")}<output>{runtime.model_executed === true ? t("是") : t("否")}</output></label></div>
    <div className="coordinate-row"><label>{t("源码对象")}<output>{nodes.length}</output></label><label>{t("未知边界")}<output>{opaque.length}</output></label></div>
    <p className="field-help">{coverage.complete === true ? t("已验证限定范围的覆盖") : t("覆盖尚未验证")} · {branches.length}{t("个分支/循环；静态依赖不证明张量形状或运行路径。")}</p>
    {selected.map(node => <details key={label(node.id)} className="semantic-fact" open><summary>{label(node.label) || label(node.id)}</summary>
      <dl className="parameters"><div><dt>{t("证据")}</dt><dd>{evidenceLabels[label(node.evidence_status)] ?? label(node.evidence_status)}</dd></div>
        {!!node.operator && <div><dt>{t("操作")}</dt><dd>{label(node.operator)}</dd></div>}
        {!!node.semantic_type && <div><dt>{t("结构")}</dt><dd>{label(node.semantic_type)}</dd></div>}
        {!!node.module_path && <div><dt>{t("模块路径")}</dt><dd>{label(node.module_path)}</dd></div>}
        {!!node.reason && <div><dt>{t("边界原因")}</dt><dd>{label(node.reason)}</dd></div>}
      </dl>
      {rows(node.source).map((span, index) => <p className="field-help" key={index}>{label(span.file)}:{Number(span.line)}–{Number(span.end_line)}</p>)}
      {!!node.iteration_contract && <details><summary>{t("迭代绑定契约")}</summary><pre>{JSON.stringify(node.iteration_contract, null, 2)}</pre></details>}
      {!!node.repeat_contract && <details><summary>{t("重复实例与共享关系")}</summary><pre>{JSON.stringify(node.repeat_contract, null, 2)}</pre></details>}
      {!!node.module_binding && <details><summary>{t("模块身份依据")}</summary><pre>{JSON.stringify(node.module_binding, null, 2)}</pre></details>}
    </details>)}
    <details><summary>{t("语义契约 ·")}{contracts.length}</summary>{contracts.length ? contracts.map((contract, index) => <div key={label(contract.id) || index}>
      <button className="text-button" onClick={() => focus(contract.node)}>{label(contract.rule) || label(contract.id)}</button>
      <p className="field-help">{label(contract.scope)}</p><ul>{(Array.isArray(contract.proof) ? contract.proof : []).map((proof, i) => <li key={i}>{String(proof)}</li>)}</ul>
      {Array.isArray(contract.not_asserted) && <p className="field-help">{t("未断言：")}{contract.not_asserted.map(String).join('、')}</p>}
    </div>) : <p className="field-help">{t("当前源码没有满足证明条件的语义契约。")}</p>}</details>
    <details><summary>{t("结构模式 ·")}{motifs.length}</summary>{motifs.map((motif, index) => {
      const target = byId.has(label(motif.id)) ? motif.id : Array.isArray(motif.members) ? motif.members.find(id => byId.has(label(id))) : undefined;
      return <div key={label(motif.id) || index}><button className="text-button" disabled={!target} onClick={() => focus(target)}>{label(motif.label) || label(motif.semantic_type) || label(motif.kind) || label(motif.id)}</button><p className="field-help">{JSON.stringify(motif.evidence ?? [])}</p></div>;
    })}</details>
    <details><summary>{t("未知边界与覆盖限制 ·")}{opaque.length + blockers.length}</summary>{opaque.map(node => <div key={label(node.id)}><button className="text-button" onClick={() => focus(node.id)}>{label(node.label)}</button><p className="field-help">{label(node.reason)}</p></div>)}{blockers.map((item, index) => <p className="field-help" key={index}>{label(item.file)}:{Number(item.line) || '—'} · {label(item.kind)}</p>)}</details>
    <button className="full-button" onClick={onEvidence}>{t("查看源码与完整证据")}</button>
    <p className="field-help">{t("源码变更通过模型编辑和事务审查提交。")}</p>
  </details>;
}
