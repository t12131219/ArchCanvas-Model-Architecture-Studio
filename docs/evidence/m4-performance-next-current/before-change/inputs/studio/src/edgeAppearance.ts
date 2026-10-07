import type { CanvasDocument, Scene } from './core/types.ts';
import { effectiveEdgeAppearance } from './core/edgePresentation.ts';

/** Read the displayed binding, retaining the selected canonical edit target. */
export function edgeAppearance(document: CanvasDocument, edgeId: string, scene: Scene) {
  const displayed = scene.edges.find(edge => edge.canonicalEdgeIds.includes(edgeId));
  if (displayed) return { stroke: displayed.stroke, width: displayed.width, dashed: displayed.dashed,
    ...(displayed.dashPattern === undefined ? {} : { dashPattern: [...displayed.dashPattern] }) };
  const canonical = document.architecture.edges.find(edge => edge.id === edgeId);
  if (!canonical) throw new Error(`Unknown canonical edge ${edgeId}`);
  return effectiveEdgeAppearance(document.pageSpec.preset, canonical.role, document.edgeStyleOverrides[edgeId]);
}
