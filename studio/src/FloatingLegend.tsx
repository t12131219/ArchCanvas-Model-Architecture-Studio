import { useState } from 'react';
import type { LegendItem, SceneEdge } from './core/types';
import { Icon } from './icons';
import { edgeDashPattern, edgeAppearanceKey } from './core/edgePresentation.ts';

const ROLE_LABELS = { data: '数据流', residual: '残差', memory: 'Memory', mask: 'Mask' };
/** Screen-space chrome: never contributes geometry or intercepts canvas gestures. */
export function FloatingLegend({ scene, onEdit }: { scene: { legend: readonly LegendItem[]; edges: readonly Pick<SceneEdge, 'role' | 'stroke' | 'width' | 'dashed' | 'dashPattern'>[] }; onEdit?: () => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const variants = [...new Map(scene.edges.map(edge => [JSON.stringify([edge.role, edgeAppearanceKey(edge)]), edge])).values()];
  return <aside className={`floating-legend ${collapsed ? 'collapsed' : ''}`} aria-label="悬浮图例"
    onPointerDown={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}
    onWheel={event => event.stopPropagation()}>
    <button className="legend-toggle" aria-expanded={!collapsed} aria-label={collapsed ? '展开悬浮图例' : '收起悬浮图例'} onClick={() => setCollapsed(value => !value)}>
      <Icon name="layers" size={14} /><b>图例</b><span>{collapsed ? '‹' : '›'}</span>
    </button>
    {!collapsed && <div className="floating-legend-content">
      <div className="floating-node-legend">{scene.legend.map(item => <div key={item.id} data-floating-legend-id={item.id}>
        <i style={{ background: item.color }} data-glyph={item.glyph}>{item.glyph === 'add' ? '+' : item.glyph === 'attention' ? '≋' : item.glyph === 'tensor' ? '▦' : '▯'}</i><span>{item.label}</span>
      </div>)}</div>
      {!!variants.length && <div className="floating-edge-legend">{variants.map((edge, index) => <div key={`${edge.role}-${index}`}>
        <svg width="38" height="14" aria-hidden="true"><path d="M 1 7 H 32" fill="none" stroke={edge.stroke} strokeWidth={Math.min(4, edge.width)} strokeDasharray={edgeDashPattern(edge)?.join(' ')} /><path d="M 28 4 L 33 7 L 28 10" fill="none" stroke={edge.stroke} /></svg><span>{ROLE_LABELS[edge.role]}</span>
      </div>)}</div>}
      {onEdit && <button className="legend-edit" onClick={onEdit}>编辑图例</button>}
    </div>}
  </aside>;
}
