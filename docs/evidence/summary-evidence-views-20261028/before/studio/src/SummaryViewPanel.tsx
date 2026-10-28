import type { PreviewSnapshot } from './PreviewStudio';

type Role = { node: string; certificate: string; role: string[]; target: string; label: string };
type View = {
  granularity: string; sequence: string; readSummary: string; frames: string; canBack: boolean;
  nodeAccounting: Record<string, string[]>; edgeAccounting: Record<string, string[]>;
  roleRequests: Role[]; roleOptions: Role[]; contracts: { id: string; node: string; rule?: string }[];
  relations: { id: string; node?: string; members?: string[]; type: string }[];
  recipe: { nested_candidates: string[]; role_paths: unknown[]; nested_deferred: unknown[]; stage_requests: string[]; scope: string } | null;
  routing: { pending: number; failed: number; complete: boolean } | null;
  selectionDetails?: { id: string; evidence: string; frameOwnership: unknown[]; repeatGroups: { index: number; indices: number[] }[] }[];
};

/** Controls project the committed Summary snapshot and send semantic-view commands. */
export function SummaryViewPanel({ snapshot, selectedIds, disabled, onCommand, onFocus, onContinue }: {
  snapshot: PreviewSnapshot | null; selectedIds: string[]; disabled: boolean;
  onCommand: (payload: Record<string, unknown>) => void; onFocus: (id: string) => void;
  onContinue?: () => void;
}) {
  const view = snapshot?.semanticView as View | undefined;
  if (!view) return null;
  const patch = (value: Record<string, unknown>) => onCommand({ patch: value });
  const roles = view.roleOptions.filter(role => selectedIds.includes(role.node) || selectedIds.includes(role.target));
  const contracts = view.contracts.filter(contract => selectedIds.includes(contract.node));
  const relations = view.relations.filter(relation => selectedIds.includes(relation.node ?? '') || relation.members?.some(id => selectedIds.includes(id)));
  return <details className="inspector-section summary-view">
    <summary>Summary 语义切面<span className="read-only">同一原生 IR</span></summary>
    <label className="field-label">切面<select aria-label="Summary 语义切面" disabled={disabled} value={view.granularity} onChange={event => patch({ paperGranularity: event.target.value })}>
      {Object.entries({ overview: '总览', modules: '模块', stages: '阶段', semantic: '语义边界', roles: '角色', detailed: '值链与细节' }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    <label className="field-label">重复结构<select aria-label="Summary 重复结构" disabled={disabled} value={view.sequence} onChange={event => patch({ paperSequenceView: event.target.value })}><option value="representatives">代表与后续调用</option><option value="summary">序列摘要</option></select></label>
    <label className="field-label">绑定展示<select aria-label="Summary 绑定展示" disabled={disabled} value={view.readSummary} onChange={event => patch({ paperReadSummary: event.target.value })}><option value="bindings">运算与绑定</option><option value="boundary">调用边界</option></select></label>
    <label className="field-label">来源外框<select aria-label="Summary 来源外框" disabled={disabled} value={view.frames} onChange={event => patch({ paperFrameView: event.target.value })}><option value="compact">合并冗余外框</option><option value="source">源码外框</option></select></label>
    <button className="full-button" disabled={disabled || !view.canBack} onClick={() => onCommand({ back: true })}>返回上个语义切面</button>
    {view.recipe && <details><summary>F1 认证细化记录</summary><p className="field-help">{view.recipe.nested_candidates.length} 个候选边界 · {view.recipe.role_paths.length} 条角色路径 · {view.recipe.stage_requests.length} 个阶段；{view.recipe.nested_deferred.length} 个边界保留独立展开。</p><pre>{JSON.stringify(view.recipe, null, 2)}</pre></details>}
    {!!contracts.length && <button className="full-button" disabled={disabled} onClick={() => patch({ paperRoleDetails: [...new Set(contracts.map(contract => contract.node))] })}>展开所选边界的认证角色</button>}
    {roles.map(role => <div key={JSON.stringify([role.node, role.certificate, role.role])}>
      <button className="full-button" disabled={disabled} onClick={() => patch({ paperRolePaths: [...view.roleRequests.filter(request => request.node !== role.node || request.certificate !== role.certificate || JSON.stringify(request.role) !== JSON.stringify(role.role)), { node: role.node, certificate: role.certificate, role: role.role }] })}>细化路径 · {role.label}</button>
      <button className="text-button" disabled={disabled} onClick={() => onFocus(role.target)}>定位原始角色</button>
    </div>)}
    {relations.map(relation => <button className="full-button" key={relation.id} disabled={disabled} onClick={() => patch({ paperRelation: relation.id, paperGranularity: 'detailed' })}>关系详图 · {relation.type}</button>)}
    {view.selectionDetails?.map(detail => <div key={detail.id}>
      {detail.repeatGroups.map(group => <button key={group.index} className="full-button" disabled={disabled} onClick={() => patch({ paperFocus: detail.id, paperRepresentative: true, paperRepresentativeGroup: group.index, paperGranularity: 'modules' })}>结构代表 · {group.indices.map(index => index + 1).join(', ')}</button>)}
      {!!detail.frameOwnership.length && <details><summary>来源外框与资源归属</summary><pre>{JSON.stringify(detail.frameOwnership, null, 2)}</pre><button className="full-button" disabled={disabled} onClick={() => patch({ paperFrameView: 'source' })}>恢复源码外框</button></details>}
      <details><summary>所选图元的完整证据与路径过程</summary><pre>{detail.evidence}</pre></details>
    </div>)}
    <details><summary>原始节点与依赖归属</summary><p className="field-help">摘要、附属、折叠和不可见对象仍保留在同一 IR 中；每个原始对象有且只有一项归属。</p>
      <pre>{JSON.stringify({ nodes: Object.fromEntries(Object.entries(view.nodeAccounting).map(([key, ids]) => [key, ids.length])), edges: Object.fromEntries(Object.entries(view.edgeAccounting).map(([key, ids]) => [key, ids.length])) }, null, 2)}</pre>
    </details>
    {!!view.routing && (view.routing.pending > 0 || view.routing.failed > 0) && <p className="field-help" role="status">布线尚未完成：{view.routing.pending} 条待处理，{view.routing.failed} 条冲突。</p>}
    {!!view.routing && (view.routing.pending > 0 || view.routing.failed > 0) && <button className="full-button" disabled={disabled} onClick={onContinue}>继续未完成布线 · {view.routing.pending + view.routing.failed}</button>}
    <p className="field-help">{snapshot?.importedDocument ? '导入文档与其中的运行记录仅作声明证据；尚未验证 Python 源码，也未执行模型。视觉编辑保存在浏览器，编辑 JSON 包含原始文档。' : '语义摘要不表示已执行模型。参数和结构修改仍通过正式编辑与事务审查。'}</p>
  </details>;
}
