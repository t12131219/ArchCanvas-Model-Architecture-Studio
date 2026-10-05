import type { Glyph } from './types.ts';

/** Versioned, source-independent visual grammar. No model names are special cased. */
export const VISUAL_VERSION = '1.0';
export const TOKENS = {
  // Cairo's SVG toy-font path selects one family for a text element rather
  // than performing browser-style per-glyph fallback. This family covers the
  // shared Latin/CJK scene on hosts with the publication font installed.
  font: 'Noto Sans CJK SC, Inter, Noto Sans, Arial, sans-serif',
  ink: '#24384b', muted: '#768697', border: '#9baabb',
  titleSize: 19, labelSize: 13, subtitleSize: 10,
  padding: 30, header: 46, gapX: 42, gapY: 38, nodeWidth: 194, nodeHeight: 62,
};
export const CATEGORY_STYLES: Record<string, { fill: string; stroke: string; glyph: Glyph }> = {
  container: { fill: '#f5f8fc', stroke: '#94a6ba', glyph: 'module' },
  module: { fill: '#edf2fa', stroke: '#7e95b5', glyph: 'module' },
  attention: { fill: '#e5eafb', stroke: '#8294cf', glyph: 'attention' },
  linear: { fill: '#e5f1ed', stroke: '#82a897', glyph: 'operator' },
  activation: { fill: '#f9eddc', stroke: '#c9a272', glyph: 'operator' },
  norm: { fill: '#f5e7ef', stroke: '#c192ad', glyph: 'norm' },
  residual: { fill: '#f4eddf', stroke: '#baa986', glyph: 'add' },
  input: { fill: '#eef2f5', stroke: '#98a6b1', glyph: 'tensor' },
  output: { fill: '#eef2f5', stroke: '#98a6b1', glyph: 'tensor' },
  tensor: { fill: '#eef2f5', stroke: '#98a6b1', glyph: 'tensor' },
  opaque: { fill: '#f5f3f1', stroke: '#a6a09a', glyph: 'opaque' },
};
export const EDGE_COLORS = { data: '#718495', residual: '#b69967', memory: '#8e91c3', mask: '#a194a8' };
