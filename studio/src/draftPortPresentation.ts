import type { DraftFlow, DraftPort } from './authoring.ts';
import { textWidth } from './core/typography.ts';
import type { PortLayout } from './core/types.ts';

/** Side-port hits cover the dot and label; vertical hits reserve peer space.
 * Vertical label text also receives events on the owning port group. */
export function draftPortPresentation(port: DraftPort, x: number, y: number, flow: DraftFlow, peerSpacing = Infinity, fontSize = 9, compact = false, side?: PortLayout['side']) {
  const input = side ? side === 'left' || side === 'top' : port.direction === 'in';
  // The catalog-driven side slots leave room for compensated overview text;
  // this cap also keeps callers with narrower custom slots from colliding.
  const labelFontSize = flow === 'horizontal' ? Math.min(fontSize, peerSpacing * .75) : fontSize;
  // Vertical labels sit outside the card and on opposite sides of the flow
  // line, leaving the bottom kind caption and top title independent.
  // The first two-input inlet sits left of the centred outlet. An exterior
  // output offset of22 leaves their label paint disjoint across short gaps.
  const labelX = x + (input ? 12 : flow === 'vertical' ? -22 : -12);
  const labelY = flow === 'vertical' ? input ? y - 4 : y + labelFontSize + 4 : y + labelFontSize / 3;
  const labelWidth = textWidth(port.name, labelFontSize);
  const left = Math.max(flow === 'vertical' ? x - peerSpacing / 2 : -Infinity,
    Math.min(x - 14, input ? labelX - 4 : labelX - labelWidth - 4));
  const right = Math.min(flow === 'vertical' ? x + peerSpacing / 2 : Infinity,
    Math.max(x + 14, input ? labelX + labelWidth + 4 : labelX + 4));
  const halfHeight = flow === 'horizontal' ? Math.min(14, peerSpacing / 2) : 14;
  // Source-derived Input/Output cards can be shorter than the normal draft
  // card. Their labels would otherwise make the transparent hitbox overlap
  // the title/body drag area. Keep keyboard focus on the group, but make the
  // pointer target a small dot-sized region for these compact cards.
  const hit = compact ? { x: x - 11, y: y - 11, width: 22, height: 22 } : { x: left, y: y - halfHeight, width: right - left, height: halfHeight * 2 };
  return { labelX, labelY, labelFontSize, textAnchor: input ? 'start' as const : 'end' as const,
    hit };
}
