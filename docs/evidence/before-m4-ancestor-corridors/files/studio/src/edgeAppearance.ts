import type { CanvasDocument, Scene } from './core/types.ts';
import { EDGE_COLORS } from './core/tokens.ts';

/** Read the displayed binding, retaining the selected canonical edit target. */
export function edgeAppearance(document: CanvasDocument, edgeId: string, scene: Scene) {
  const displayed = scene.edges.find(edge => edge.canonicalEdgeIds.includes(edgeId));
  if (displayed) return { stroke: displayed.stroke, width: displayed.width, dashed: displayed.dashed };
  const canonical = document.architecture.edges.find(edge => edge.id === edgeId);
  if (!canonical) throw new Error(`Unknown canonical edge ${edgeId}`);
  const override = document.edgeStyleOverrides[edgeId] ?? {};
  return {
    stroke: document.pageSpec.preset === 'monochrome' ? '#56616b' : override.stroke ?? EDGE_COLORS[canonical.role],
    width: override.width ?? 1.5,
    dashed: override.dashed ?? canonical.role === 'mask',
  };
}
