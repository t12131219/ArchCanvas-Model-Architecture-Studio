import type { DraftFlow, DraftPort } from './authoring.ts';
import { textWidth } from './core/typography.ts';

/** One hit region covers the visible circle, label, and the gap between them. */
export function draftPortPresentation(port: DraftPort, x: number, y: number, flow: DraftFlow, peerSpacing = Infinity, fontSize = 9) {
  const input = port.direction === 'in';
  // Side ports share a small vertical slot; text compensation must not make
  // neighboring input names collide inside that slot.
  const labelFontSize = flow === 'horizontal' ? Math.min(fontSize, peerSpacing * .75) : fontSize;
  // Vertical labels sit on opposite sides of the flow line; adjacent cards'
  // input/output labels remain legible even with a short inter-card gap.
  const labelX = x + (input ? 12 : -12), labelY = y + labelFontSize / 3;
  const labelWidth = textWidth(port.name, labelFontSize);
  const left = Math.max(flow === 'vertical' ? x - peerSpacing / 2 : -Infinity,
    Math.min(x - 14, input ? labelX - 4 : labelX - labelWidth - 4));
  const right = Math.min(flow === 'vertical' ? x + peerSpacing / 2 : Infinity,
    Math.max(x + 14, input ? labelX + labelWidth + 4 : labelX + 4));
  const halfHeight = flow === 'horizontal' ? Math.min(14, peerSpacing / 2) : 14;
  return { labelX, labelY, labelFontSize, textAnchor: input ? 'start' as const : 'end' as const,
    hit: { x: left, y: y - halfHeight, width: right - left, height: halfHeight * 2 } };
}
