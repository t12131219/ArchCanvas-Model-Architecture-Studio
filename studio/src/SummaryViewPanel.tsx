import { t } from './i18n';
import { useEffect, useState } from 'react';
import type { PreviewSnapshot } from './PreviewStudio';

type Module = { id: string; label: string; parent: string | null; count: number; maxDepth: number };
export type SummaryView = {
  legacy?: boolean; mode?: string;
  modules?: Module[];
  moduleCuts?: { id: string; level: string; depth?: number }[];
  mixed?: { scopes: { id: string; level: string; depth: number | null; canonicalNodes: number; visibleNodes: number }[] } | null;
  suggestedModules?: string[];
  routing?: { pending: number; failed: number; complete: boolean } | null;
};
type VisibleNode = { id: string; parent?: string | null; expanded?: boolean };

/** Read the committed expansion, including direct canvas/tree gestures. */
export function summaryModuleDepth(view: SummaryView, target: Module, nodes: VisibleNode[]): number {
  const cut = view.moduleCuts?.find(cut => cut.id === target.id);
  if (cut?.level === 'source') return Math.min(target.maxDepth, cut.depth ?? target.maxDepth);
  const by = new Map(nodes.map(node => [node.id, node]));
  let depth = 0;
  for (const node of nodes.filter(node => node.expanded)) {
    let at: VisibleNode | undefined = node, distance = 1;
    const seen = new Set<string>();
    while (at && !seen.has(at.id)) {
      if (at.id === target.id) { depth = Math.max(depth, distance); break; }
      seen.add(at.id); at = at.parent ? by.get(at.parent) : undefined; distance++;
    }
  }
  return Math.min(target.maxDepth, depth);
}

/** One graph: every command addresses just the chosen module. */
export function SummaryViewPanel({ snapshot, disabled, onCommand, onFocus, onContinue }: {
  snapshot: PreviewSnapshot | null; selectedIds: string[]; disabled: boolean;
  onCommand: (payload: Record<string, unknown>) => void; onFocus: (id: string) => void;
  onContinue?: () => void;
}) {
  const view = snapshot?.semanticView as SummaryView | undefined;
  const [moduleTarget, setModuleTarget] = useState('');
  const [sourceDepth, setSourceDepth] = useState(1);
  const modules = view?.modules ?? [], target = modules.find(module => module.id === moduleTarget) ?? modules[0];
  const suggested = view?.suggestedModules?.[0];
  useEffect(() => { if (suggested) setModuleTarget(suggested); }, [suggested]);
  const nodes = (snapshot?.graph?.nodes ?? []) as VisibleNode[];
  const depth = view && target ? summaryModuleDepth(view, target, nodes) : 0;
  useEffect(() => { setSourceDepth(depth); }, [target?.id, depth]);
  if (!view || !target) return null;
  const applyDepth = (next: number) => onCommand({ moduleCut: { ids: [target.id], replaceDescendants: true, level: 'source', depth: Math.max(0, Math.min(target.maxDepth, next)) } });
  const routing = view.routing;
  const frontier = snapshot?.frontier as { visibleNodeCount?: number; visibleEdgeCount?: number } | undefined;
  const visible = frontier?.visibleNodeCount ?? nodes.length;
  const edges = frontier?.visibleEdgeCount ?? (snapshot?.graph?.edges as unknown[] | undefined)?.length ?? 0;
  return <details className="inspector-section summary-view" open>
    <summary>{t("模块展开")}<span className="read-only">{t("同一张图")}</span></summary>
    <div className="coordinate-row"><label>{t("节点")}<output>{visible}</output></label><label>{t("连线")}<output>{edges}</output></label></div>
    <label className="field-label">{t("目标模块")}<select aria-label={t("Summary 目标模块")} disabled={disabled} value={target.id} onChange={event => setModuleTarget(event.target.value)}>
      {modules.map(module => <option key={module.id} value={module.id}>{module.label} · {module.count}{t("个原始节点")}{module.parent ? '' : t(" · 整个模型")}</option>)}
    </select></label>
    <button className="full-button" disabled={disabled} onClick={() => onFocus(target.id)}>{t("定位目标模块")}</button>
    <div className="coordinate-row"><button disabled={disabled || depth >= target.maxDepth} onClick={() => applyDepth(depth + 1)}>{t("展开一层")}</button><button disabled={disabled || depth === 0} onClick={() => applyDepth(depth - 1)}>{t("收起一层")}</button></div>
    <label className="field-label">{t("展开深度")}<input aria-label={t("Summary 模块展开深度")} type="number" min="0" max={target.maxDepth} disabled={disabled} value={Math.min(sourceDepth, target.maxDepth)} onChange={event => setSourceDepth(Math.max(0, Math.min(target.maxDepth, Number(event.target.value) || 0)))}/></label>
    <button className="full-button" disabled={disabled} onClick={() => applyDepth(sourceDepth)}>{t("应用深度")}</button>
    <div className="coordinate-row"><button disabled={disabled} onClick={() => onCommand({ moduleCut: { ids: [target.id], replaceDescendants: true, level: 'source' } })}>{t("全部展开")}</button><button disabled={disabled} onClick={() => applyDepth(0)}>{t("收起模块")}</button></div>
    <p className="field-help">{t("只调整目标模块，其他模块保留各自的展开状态。可在画布或左侧层级中继续展开。")}</p>
    <details className="summary-expansion-presets"><summary>{t("展开预设")}</summary>
      <div className="coordinate-row"><button disabled={disabled} onClick={() => onCommand({ moduleCut: { ids: [target.id], replaceDescendants: true, level: 'f0' } })}>{t("架构概览")}</button><button disabled={disabled} onClick={() => onCommand({ moduleCut: { ids: [target.id], replaceDescendants: true, level: 'f1' } })}>{t("模块详图")}</button></div>
      <button className="full-button" disabled={disabled} onClick={() => onCommand({ moduleCut: { ids: [target.id], replaceDescendants: true, reset: true } })}>{t("恢复目标模块默认展开")}</button>
    </details>
    {!!view.mixed?.scopes.length && <details className="summary-expansion-state"><summary>{t("各模块展开状态 ·")}{view.mixed.scopes.length}</summary>
      {view.mixed.scopes.map(scope => <div key={scope.id} className="semantic-fact" data-module-id={scope.id} data-module-level={scope.level} data-module-depth={scope.depth ?? 'all'}>
        <button className="text-button" disabled={disabled} onClick={() => setModuleTarget(scope.id)}>{modules.find(module => module.id === scope.id)?.label ?? scope.id}</button>
        <p className="field-help">{scope.level === 'source' ? scope.depth === null ? t("全部展开") : t("深度 {0}", {"0": scope.depth}) : scope.level === 'f0' ? t("架构概览预设") : scope.level === 'f1' ? t("模块详图预设") : t("语义展开")} · {scope.visibleNodes}{t("可见 /")}{scope.canonicalNodes}{t("原始节点")}</p>
      </div>)}
    </details>}
    {routing && !routing.complete && <><p className="field-help" role="status">{t("布线尚未完成：")}{routing.pending}{t("条待处理，")}{routing.failed}{t("条冲突。")}</p><button className="full-button" disabled={disabled} onClick={onContinue}>{t("继续未完成布线 ·")}{routing.pending + routing.failed}</button></>}
  </details>;
}
