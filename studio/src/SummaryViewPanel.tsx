import { useEffect, useState } from 'react';
import type { PreviewSnapshot } from './PreviewStudio';

type Role = { node: string; certificate: string; role: string[]; target: string; label: string };
type View = {
  legacy?: boolean; mode?: string; availableModes?: string[];
  modules?: { id: string; label: string; parent: string | null; count: number; maxDepth: number }[];
  moduleCuts?: { id: string; level: string; depth?: number }[];
  mixed?: { scopes: { id: string; level: string; depth: number | null; canonicalNodes: number; visibleNodes: number }[] } | null;
  suggestedModules?: string[];
  runtimeEvidence?: { runs: { index: number; case: string; mode: string; status: string; truncated: boolean; replayMatched: boolean }[];
    selectedRun: number; integratedRegions: number; unplacedRegions: number; traceDigest: string | null; sourceUnchanged: boolean; executesModel: false };
  granularity: string; sequence: string; readSummary: string; frames: string; canBack: boolean;
  nodeAccounting: Record<string, string[]>; edgeAccounting: Record<string, string[]>;
  roleRequests: Role[]; roleDetails?: string[]; roleOptions: Role[]; contracts: { id: string; node: string; rule?: string }[];
  relations: { id: string; node?: string; members?: string[]; type: string }[];
  recipe: { nested_candidates: string[]; role_paths: unknown[]; nested_deferred: unknown[]; stage_requests: string[]; scope: string } | null;
  routing: { pending: number; failed: number; complete: boolean } | null;
  adaptive?: { enabled: boolean; policy: string; eligible: boolean; receipt: { restored?: boolean; attempts?: { accepted: boolean }[]; selected_role_paths: unknown[]; selected_role_details: string[]; selected_expression_details: string[] } | null };
  selectionDetails?: { id: string; evidence: string; frameOwnership: unknown[]; repeatGroups: { index: number; indices: number[] }[] }[];
};

/** Controls project the committed Summary snapshot and send semantic-view commands. */
export function SummaryViewPanel({ snapshot, selectedIds, disabled, onCommand, onFocus, onContinue }: {
  snapshot: PreviewSnapshot | null; selectedIds: string[]; disabled: boolean;
  onCommand: (payload: Record<string, unknown>) => void; onFocus: (id: string) => void;
  onContinue?: () => void;
}) {
  const view = snapshot?.semanticView as View | undefined;
  const [moduleTarget, setModuleTarget] = useState('');
  const [moduleLevel, setModuleLevel] = useState('f1');
  const [sourceDepth, setSourceDepth] = useState(1);
  const suggested = view?.suggestedModules?.join('|') ?? '';
  useEffect(() => { if (view?.suggestedModules?.[0]) setModuleTarget(view.suggestedModules[0]); }, [suggested]);
  const currentCut = view?.moduleCuts?.find(cut => cut.id === moduleTarget);
  const currentMaxDepth = view?.modules?.find(module => module.id === moduleTarget)?.maxDepth;
  useEffect(() => {
    setModuleLevel(currentCut?.level ?? 'f1');
    if (currentCut?.depth !== undefined) setSourceDepth(currentCut.depth);
    else if (currentCut?.level === 'source' && currentMaxDepth !== undefined) setSourceDepth(currentMaxDepth);
  }, [moduleTarget, currentCut?.level, currentCut?.depth, currentMaxDepth, view?.legacy]);
  if (!view) return null;
  const patch = (value: Record<string, unknown>) => onCommand({ patch: value });
  const roles = view.roleOptions.filter(role => selectedIds.includes(role.node) || selectedIds.includes(role.target));
  const contracts = view.contracts.filter(contract => selectedIds.includes(contract.node));
  const relations = view.relations.filter(relation => selectedIds.includes(relation.node ?? '') || relation.members?.some(id => selectedIds.includes(id)));
  const runtime = view.runtimeEvidence, mode = view.mode ?? 'source';
  const modules = view.modules ?? [], target = modules.find(module => module.id === moduleTarget) ?? modules[0];
  const moduleCommand = (level: string, depth?: number) => target && onCommand({ moduleCut: { ids: [target.id], level, ...(depth !== undefined ? { depth } : {}) } });
  const levelNames: Record<string, string> = { f0: 'F0 架构概览', f1: view.legacy ? 'F1 登记详图' : 'F1 认证详图', overview: '总览', modules: '模块', stages: '阶段', semantic: '语义边界', roles: '角色', detailed: '值链与细节', source: view.legacy ? '登记原子层' : '源码原子层' };
  return <details className="inspector-section summary-view">
    <summary>Summary 语义切面<span className="read-only">{view.legacy ? '登记预览层级' : '同一原生 IR'}</span></summary>
    {!!modules.length && <details className="summary-module-depth" open>
      <summary>模块语义深度<span className="read-only">{view.moduleCuts?.length ?? 0} 个独立切面</span></summary>
      <p className="field-help">选中模块后单独调整；其他模块保留各自的切面。源码深度可逐级增加，或一次展开全部原始节点。</p>
      <label className="field-label">目标模块<select aria-label="Summary 目标模块" disabled={disabled} value={target?.id ?? ''} onChange={event => setModuleTarget(event.target.value)}>
        {modules.map(module => <option key={module.id} value={module.id}>{module.label} · {module.count} 原始节点{module.parent ? '' : ' · 整个模型'}</option>)}
      </select></label>
      <button className="full-button" disabled={disabled || !target} onClick={() => target && onFocus(target.id)}>定位目标模块</button>
      <label className="field-label">模块切面<select aria-label="Summary 模块切面" disabled={disabled} value={moduleLevel} onChange={event => setModuleLevel(event.target.value)}>
        {Object.entries(levelNames).filter(([value]) => !view.legacy || ['f0', 'f1', 'source'].includes(value)).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      {moduleLevel === 'source' && <label className="field-label">源码层数<input aria-label="Summary 模块源码层数" type="number" min="0" max={target?.maxDepth ?? 1} value={Math.min(sourceDepth, target?.maxDepth ?? 1)} onChange={event => setSourceDepth(Math.max(0, Math.min(target?.maxDepth ?? 1, Number(event.target.value) || 0)))}/></label>}
      <button className="full-button" disabled={disabled || !target} onClick={() => moduleCommand(moduleLevel, moduleLevel === 'source' ? Math.min(sourceDepth, target?.maxDepth ?? 1) : undefined)}>应用到目标模块</button>
      <div className="coordinate-row"><button disabled={disabled || !target} onClick={() => moduleCommand('f0')}>模块 F0</button><button disabled={disabled || !target} onClick={() => moduleCommand('f1')}>模块 F1</button></div>
      <button className="full-button" disabled={disabled || !target} onClick={() => moduleCommand('source')}>{view.legacy ? '目标模块展开到全部登记原子' : '目标模块展开到全部源码原子'}</button>
      <button className="full-button" disabled={disabled || !view.moduleCuts?.some(cut => cut.id === target?.id)} onClick={() => onCommand({ moduleCut: { ids: [target!.id], reset: true } })}>目标模块恢复全局切面</button>
      {view.mixed?.scopes.map(scope => <div key={scope.id} className="semantic-fact" data-module-id={scope.id} data-module-level={scope.level} data-module-depth={scope.depth ?? 'all'}><button className="text-button" disabled={disabled} onClick={() => { setModuleTarget(scope.id); setModuleLevel(scope.level); if (scope.depth !== null) setSourceDepth(scope.depth); }}>{modules.find(module => module.id === scope.id)?.label ?? scope.id}</button><p className="field-help">{levelNames[scope.level]}{scope.depth !== null ? ` · ${scope.depth} 层` : ''} · {scope.visibleNodes} 可见 / {scope.canonicalNodes} 原始节点</p></div>)}
      <p className="field-help">全局 F0/F1 与展开/收起全部会统一重设前沿；撤销、重做及编辑 JSON 保留混合切面。</p>
    </details>}
    {!view.legacy && <>
    <label className="field-label">证据视图<select aria-label="Summary 证据视图" disabled={disabled} value={mode} onChange={event => patch({ mode: event.target.value, paperFocus: null, paperRelation: null })}>
      {Object.entries({ source: '源码', runtime: 'CPU 轨迹', merged: '合并' }).map(([value,label]) => <option key={value} value={value} disabled={!(view.availableModes ?? ['source']).includes(value)}>{label}</option>)}
    </select></label>
    {mode === 'merged' && !!runtime?.runs.length && <label className="field-label">CPU 补证样例<select aria-label="Summary CPU 补证样例" disabled={disabled} value={runtime.selectedRun} onChange={event => patch({ runtimeInlineRun: Number(event.target.value), paperFocus: null })}>
      {runtime.runs.map(run => <option key={run.index} value={run.index}>{run.case} / {run.mode} · {run.status === 'passed' ? '记录通过' : run.status === 'failed' ? '记录失败' : run.status}{run.truncated ? ' · 已截断' : ''}</option>)}
    </select></label>}
    {runtime && <p className="field-help">{runtime.runs.length ? `${runtime.runs.length} 个文档内运行样例；${mode === 'runtime' ? 'CPU 轨迹显示原始运行记录。' : mode === 'merged' ? runtime.integratedRegions ? `所选样例接入 ${runtime.integratedRegions} 个可核对的源码调用。` : '所选记录没有可唯一核对的调用绑定，源码边界保持原样；可切换 CPU 轨迹查看完整记录。' : '当前只展示源码，运行记录保留在原始 IR 中。'}` : '当前没有运行记录；合并视图保留源码事实。'} 切换视图不会运行模型，未观察的路径仍未知。</p>}
    <label className="field-label">切面<select aria-label="Summary 语义切面" disabled={disabled} value={view.granularity} onChange={event => patch({ paperGranularity: event.target.value })}>
      {Object.entries({ overview: '总览', modules: '模块', stages: '阶段', semantic: '语义边界', roles: '角色', detailed: '值链与细节' }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    <label className="check"><input type="checkbox" aria-label="Summary 局部自适应细化" disabled={disabled || !view.adaptive?.eligible} checked={view.adaptive?.enabled === true} onChange={event => patch({ paperAdaptive: event.target.checked })}/>局部自适应细化</label>
    {view.adaptive?.enabled && <label className="field-label">细化目标<select aria-label="Summary 自适应策略" disabled={disabled} value={view.adaptive.policy} onChange={event => patch({ paperAdaptivePolicy: event.target.value })}><option value="detail">局部关系细节</option><option value="structure">结构与角色路径</option></select></label>}
    {view.adaptive?.receipt && <details className="summary-adaptive-receipt"><summary>自适应细化测量记录</summary><p className="field-help">{view.adaptive.receipt.restored ? '已恢复保存的细化请求与独立校验的布局。' : `${view.adaptive.receipt.attempts?.length ?? 0} 个实际布线候选，${view.adaptive.receipt.attempts?.filter(attempt => attempt.accepted).length ?? 0} 个采用。`} 开启不保证增加细节；手动角色编辑保留当前选择并关闭自动细化。</p><pre>{JSON.stringify(view.adaptive.receipt, null, 2)}</pre></details>}
    <label className="field-label">重复结构<select aria-label="Summary 重复结构" disabled={disabled} value={view.sequence} onChange={event => patch({ paperSequenceView: event.target.value })}><option value="representatives">代表与后续调用</option><option value="summary">序列摘要</option></select></label>
    <label className="field-label">绑定展示<select aria-label="Summary 绑定展示" disabled={disabled} value={view.readSummary} onChange={event => patch({ paperReadSummary: event.target.value })}><option value="bindings">运算与绑定</option><option value="boundary">调用边界</option></select></label>
    <label className="field-label">来源外框<select aria-label="Summary 来源外框" disabled={disabled} value={view.frames} onChange={event => patch({ paperFrameView: event.target.value })}><option value="compact">合并冗余外框</option><option value="source">源码外框</option></select></label>
    <button className="full-button" disabled={disabled || !view.canBack} onClick={() => onCommand({ back: true })}>返回上个语义切面</button>
    {view.recipe && <details><summary>F1 认证细化记录</summary><p className="field-help">{view.recipe.nested_candidates.length} 个候选边界 · {view.recipe.role_paths.length} 条角色路径 · {view.recipe.stage_requests.length} 个阶段；{view.recipe.nested_deferred.length} 个边界保留独立展开。</p><pre>{JSON.stringify(view.recipe, null, 2)}</pre></details>}
    {!!contracts.length && <button className="full-button" disabled={disabled} onClick={() => patch({ paperRoleDetails: [...new Set([...(view.roleDetails ?? []), ...contracts.map(contract => contract.node)])] })}>展开所选边界的认证角色</button>}
    {contracts.some(contract => view.roleDetails?.includes(contract.node)) && <button className="full-button" disabled={disabled} onClick={() => patch({ paperRoleDetails: (view.roleDetails ?? []).filter(id => !contracts.some(contract => contract.node === id)), paperRolePaths: view.roleRequests.filter(request => !contracts.some(contract => contract.node === request.node)) })}>收起所选边界的认证角色</button>}
    {roles.map(role => <div key={JSON.stringify([role.node, role.certificate, role.role])}>
      <button className="full-button" disabled={disabled} onClick={() => patch({ paperRolePaths: [...view.roleRequests.filter(request => request.node !== role.node || request.certificate !== role.certificate || JSON.stringify(request.role) !== JSON.stringify(role.role)), { node: role.node, certificate: role.certificate, role: role.role }] })}>细化路径 · {role.label}</button>
      <button className="text-button" disabled={disabled} onClick={() => onFocus(role.target)}>定位原始角色</button>
      {view.roleRequests.some(request => request.node === role.node && request.certificate === role.certificate && JSON.stringify(request.role) === JSON.stringify(role.role)) && <button className="text-button" disabled={disabled} onClick={() => patch({ paperRolePaths: view.roleRequests.filter(request => request.node !== role.node || request.certificate !== role.certificate || JSON.stringify(request.role) !== JSON.stringify(role.role)) })}>收起路径 · {role.label}</button>}
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
    {!!runtime?.runs.length && <details><summary>CPU 记录与合并边界</summary><pre>{JSON.stringify(runtime, null, 2)}</pre><p className="field-help">这里显示文档携带的记录和匹配结果；原始 IR、完整轨迹及覆盖限制保留在证据中。正式执行与源码修改仍需各自的隔离验证和事务流程。</p></details>}
    {!!view.routing && (view.routing.pending > 0 || view.routing.failed > 0) && <p className="field-help" role="status">布线尚未完成：{view.routing.pending} 条待处理，{view.routing.failed} 条冲突。</p>}
    {!!view.routing && (view.routing.pending > 0 || view.routing.failed > 0) && <button className="full-button" disabled={disabled} onClick={onContinue}>继续未完成布线 · {view.routing.pending + view.routing.failed}</button>}
    </>}
    {view.legacy && <p className="field-help">按案例登记的原子节点、依赖和来源证据展开；折叠单位保留在原始预览 IR 中。源码分析与 CPU 执行权限仍由原有流程验证。</p>}
    <p className="field-help">{snapshot?.importedDocument ? '导入文档与其中的运行记录仅作声明证据；尚未验证 Python 源码，也未执行模型。视觉编辑保存在浏览器，编辑 JSON 包含原始文档。' : '语义摘要不表示已执行模型。参数和结构修改仍通过正式编辑与事务审查。'}</p>
  </details>;
}
