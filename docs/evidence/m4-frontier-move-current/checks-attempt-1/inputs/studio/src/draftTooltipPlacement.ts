export type DraftTooltipSide = 'left' | 'right' | 'above' | 'below';
export type DraftTooltipRect = { x: number; y: number; width: number; height: number };
export type DraftTooltipAnchor = {
  port: { x: number; y: number };
  node: DraftTooltipRect;
  direction: 'in' | 'out';
  flow: 'horizontal' | 'vertical';
};
export type DraftTooltipSize = { width: number; height: number };
export type DraftTooltipViewport = { width: number; height: number };
export type DraftTooltipPosition = { left: number; top: number; side: DraftTooltipSide };

const GAP = 18;
const MARGIN = 12;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(value, Math.max(min, max)));
}

function overlapArea(a: DraftTooltipRect, b: DraftTooltipRect) {
  return Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x))
    * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
}

/**
 * Place a port hint outside its card whenever the viewport permits it.
 * Candidates are ordered by the port's natural outward side, then by the
 * remaining sides.  Clamping is applied after candidate generation, and a
 * non-overlapping candidate always wins over one that would cover node text.
 */
export function placeDraftTooltip(anchor: DraftTooltipAnchor, size: DraftTooltipSize, viewport: DraftTooltipViewport, nodes: readonly DraftTooltipRect[] = [anchor.node]): DraftTooltipPosition {
  const maxLeft = Math.max(MARGIN, viewport.width - size.width - MARGIN);
  const maxTop = Math.max(MARGIN, viewport.height - size.height - MARGIN);
  const preferred: DraftTooltipSide = anchor.flow === 'vertical'
    ? anchor.direction === 'in' ? 'above' : 'below'
    : anchor.direction === 'in' ? 'left' : 'right';
  const order: DraftTooltipSide[] = [preferred, ...(['left', 'right', 'above', 'below'] as DraftTooltipSide[]).filter(side => side !== preferred)];
  const candidates = order.map(side => {
    const raw = side === 'left'
      ? { left: anchor.node.x - size.width - GAP, top: anchor.port.y - size.height / 2 }
      : side === 'right'
        ? { left: anchor.node.x + anchor.node.width + GAP, top: anchor.port.y - size.height / 2 }
        : side === 'above'
          ? { left: anchor.port.x - size.width / 2, top: anchor.node.y - size.height - GAP }
          : { left: anchor.port.x - size.width / 2, top: anchor.node.y + anchor.node.height + GAP };
    const position = { left: clamp(raw.left, MARGIN, maxLeft), top: clamp(raw.top, MARGIN, maxTop) };
    const rect = { x: position.left, y: position.top, width: size.width, height: size.height };
    const wasClamped = position.left !== raw.left || position.top !== raw.top;
    const coveredArea = nodes.reduce((sum, node) => sum + overlapArea(rect, node), 0);
    return { ...position, side, clear: coveredArea === 0, coveredArea, wasClamped };
  });
  const candidate = candidates.find(item => item.clear && !item.wasClamped)
    ?? candidates.find(item => item.clear)
    ?? candidates.reduce((best, item) => item.coveredArea < best.coveredArea ? item : best);
  return { left: candidate.left, top: candidate.top, side: candidate.side };
}
