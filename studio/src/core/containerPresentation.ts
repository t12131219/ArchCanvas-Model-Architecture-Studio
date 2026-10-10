/** Expanded model roots group source facts and frontier snapshots without
 * imposing a physical frame on the infinite editor canvas. */
export function implicitRootIds(scene: { nodes: readonly { id: string; parentId?: string; boundary?: boolean; expanded: boolean; expandable: boolean }[] }): Set<string> {
  return new Set(scene.nodes.filter(node => !node.parentId && !node.boundary && node.expanded && node.expandable).map(node => node.id));
}
