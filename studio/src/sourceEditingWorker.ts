import { projectSourceEditing } from './sourceEditingProjection.ts';
import type { CanvasDocument } from './core/types.ts';
import type { AuthoredDraft } from './authoring.ts';
import { sourceFrontierDocument, sourceRegionDocument } from './sourceDraftFrontier.ts';
import { buildScene } from './core/index.ts';

type ProjectionInput = { document: CanvasDocument; previousEditing?: CanvasDocument; previousView?: CanvasDocument } |
  { draft: AuthoredDraft; nodeId: string; expanded: boolean } | { draft: AuthoredDraft; canonicalId: string };
const scope = self as unknown as { onmessage: ((event: MessageEvent<ProjectionInput>) => void) | null; postMessage: (value: unknown) => void };
scope.onmessage = event => {
  try {
    const input = event.data;
    if ('draft' in input) {
      const document = 'canonicalId' in input ? sourceRegionDocument(input.draft, input.canonicalId) : sourceFrontierDocument(input.draft, input.nodeId, input.expanded);
      scope.postMessage({ result: { document, scene: buildScene(document, { presentation: 'editor' }) } });
    } else scope.postMessage({ result: projectSourceEditing(input.document, input.previousEditing, input.previousView) });
  }
  catch (reason) { scope.postMessage({ error: reason instanceof Error ? reason.message : String(reason) }); }
};
