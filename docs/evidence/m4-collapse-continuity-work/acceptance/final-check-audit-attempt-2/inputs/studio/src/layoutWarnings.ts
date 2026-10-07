import type { Scene } from './core/types.ts';

/** User-facing layout guidance is separate from canonical diagnostic evidence. */
export function layoutWarnings(scene: Scene | null): string[] {
  if (!scene) return [];
  const labels = new Map(scene.nodes.map(node => [node.id, node.label]));
  const name = (id: string | undefined) => `“${id ? labels.get(id) ?? '对象' : '对象'}”`;
  const messages = scene.diagnostics.flatMap(diagnostic => {
    const ids = diagnostic.objectIds ?? [];
    if (diagnostic.message.startsWith('Pinned object')) return [
      '固定对象与展开区域重叠。可移动对象或取消固定后重新排列。',
    ];
    if (diagnostic.code === 'layout-header-overlap') return [
      `${name(ids[0])}进入了${name(ids[1])}的标题区。向下移动该对象可恢复留白。`,
    ];
    if (diagnostic.code === 'layout-outside-parent') return [
      `${name(ids[0])}超出了${name(ids[1])}的边界。移回容器内，或预览位置修复。`,
    ];
    if (diagnostic.code === 'layout-overlap') return [
      `${name(ids[0])}与${name(ids[1])}重叠。移动其中一个对象，或增大间距。`,
    ];
    if (diagnostic.code === 'layout-route-blocked') {
      const edge = scene.edges.find(item => item.id === diagnostic.edgeId);
      const target = edge ? `${name(edge.sourceId)} → ${name(edge.targetId)}` : '部分';
      return [`${target}连线缺少畅通路径。移动遮挡对象，或增大间距。`];
    }
    return [];
  });
  return [...new Set(messages)];
}
