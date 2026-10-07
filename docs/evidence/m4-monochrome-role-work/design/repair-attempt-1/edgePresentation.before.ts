import type { EdgeRole, EdgeStyle, PageSpec } from './types.ts';
import { EDGE_COLORS } from './tokens.ts';

export interface EdgeAppearance {
  stroke: string;
  width: number;
  dashed: boolean;
  /** Derived display grammar; absent on the original paper presentation. */
  dashPattern?: number[];
}

const MONO_PATTERNS: Record<EdgeRole, readonly number[]> = {
  data: [], residual: [9, 4], memory: [9, 3, 1, 3], mask: [3, 3],
};

/** User boolean overrides retain their original solid/generic-dash meaning. */
export function effectiveEdgeAppearance(preset: PageSpec['preset'], role: EdgeRole, override: EdgeStyle = {}): EdgeAppearance {
  if (preset === 'paper') return {
    stroke: override.stroke ?? EDGE_COLORS[role], width: override.width ?? 1.5,
    dashed: override.dashed ?? role === 'mask',
  };
  const dashPattern = override.dashed === undefined ? [...MONO_PATTERNS[role]] : override.dashed ? [5, 4] : [];
  return { stroke: '#56616b', width: override.width ?? 1.5, dashed: dashPattern.length > 0, dashPattern };
}

/** Legacy Scene/Route appearances have the original boolean dash grammar. */
export function edgeDashPattern(appearance: Pick<EdgeAppearance, 'dashed' | 'dashPattern'>): number[] {
  if (appearance.dashPattern === undefined) return appearance.dashed ? [5, 4] : [];
  const pattern = appearance.dashPattern;
  if (!Array.isArray(pattern) || pattern.length > 8 || pattern.length % 2 !== 0 ||
      pattern.some(value => typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || value > 100) ||
      appearance.dashed !== (pattern.length > 0)) throw new Error('Invalid derived edge dash pattern');
  return [...pattern];
}

/** Rendered style equality includes the actual pattern, not only dashed=true. */
export function edgeAppearanceKey(appearance: EdgeAppearance): string {
  return JSON.stringify([appearance.stroke, appearance.width, edgeDashPattern(appearance)]);
}

export function edgePatternLabel(appearance: Pick<EdgeAppearance, 'dashed' | 'dashPattern'>): string {
  const pattern = edgeDashPattern(appearance).join(' ');
  return pattern === '' ? '实线' : pattern === '9 4' ? '长虚线' : pattern === '9 3 1 3' ? '点划线' : pattern === '3 3' ? '短虚线' : '通用虚线';
}
