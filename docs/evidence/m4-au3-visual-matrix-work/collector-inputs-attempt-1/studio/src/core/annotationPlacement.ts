import type { Bounds, Scene } from './types.ts';
import { textWidth } from './typography.ts';

export interface AnnotationBodyConflict {
  kind: 'node' | 'legend' | 'annotation';
  id: string;
}

type AnnotationBody = Pick<Scene['annotations'][number], 'id' | 'x' | 'y' | 'width' | 'height'>;

// The legend swatch spans y - 11 through y + 4; its label starts at x + 29
// with a 10-unit font in the shared SVG renderer. Include that label's width.
function legendBody(item: Scene['legend'][number]): Bounds {
  return { x: item.x, y: item.y - 11, width: 29 + textWidth(item.label, 10), height: 15 };
}

function intersects(a: Bounds, b: Bounds): boolean {
  return a.x < b.x + b.width && a.x + a.width > b.x
    && a.y < b.y + b.height && a.y + a.height > b.y;
}

/** Suggest a new absolute position; applying it is an explicit document edit. */
export function suggestAnnotationPosition(scene: Scene, ignoreAnnotationId?: string): { x: number; y: number } {
  const annotations = scene.annotations.filter(annotation => annotation.id !== ignoreAnnotationId);
  // Scene.bounds includes annotations and page padding. Using it would make a
  // selected note push itself farther down each time the command is repeated.
  const bottom = Math.max(92,
    ...scene.nodes.map(node => node.y + node.height),
    ...scene.legend.map(item => { const body = legendBody(item); return body.y + body.height; }),
    ...annotations.map(annotation => annotation.y + annotation.height),
  );
  return {
    x: Math.min(50, ...scene.nodes.map(node => node.x), ...scene.legend.map(item => item.x)),
    y: bottom + 24,
  };
}

/** Body intersections only: routes and expanded container frames are outside this check. */
export function findAnnotationBodyConflicts(scene: Scene, annotation: AnnotationBody): AnnotationBodyConflict[] {
  const parents = new Set(scene.nodes.map(node => node.parentId).filter(id => id !== undefined));
  const conflicts: AnnotationBodyConflict[] = [];
  for (const node of scene.nodes) {
    // A collapsed container is a leaf in the current frontier. The empty space
    // inside an expanded ancestor is available for manually positioned notes.
    if (!parents.has(node.id) && intersects(annotation, node)) conflicts.push({ kind: 'node', id: node.id });
  }
  for (const item of scene.legend) {
    if (intersects(annotation, legendBody(item))) conflicts.push({ kind: 'legend', id: item.id });
  }
  for (const other of scene.annotations) {
    if (other.id !== annotation.id && intersects(annotation, other)) conflicts.push({ kind: 'annotation', id: other.id });
  }
  return conflicts;
}
