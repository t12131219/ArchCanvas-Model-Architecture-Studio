import type { Architecture, ArchitectureNode, OutputPathSegment, SourceNodeFact } from './types.ts';

/** A display of authored metadata; aliases never participate in identity grouping. */
export function instanceCalls(architecture: Architecture, node: ArchitectureNode): ArchitectureNode[] {
  if (!node.instanceId) return [];
  return [...new Map(architecture.nodes.filter(candidate => candidate.instanceId === node.instanceId && candidate.callId !== undefined)
    .map(candidate => [candidate.callId, candidate])).values()];
}

export function outputPathText(path: OutputPathSegment[]): string {
  return `return${path.map(segment => segment.kind === 'index' ? `[${segment.index}]` : `[${JSON.stringify(segment.key)}]`).join('')}`;
}

export function sourceNodeFacts(architecture: Architecture): SourceNodeFact[] {
  const calls = new Map<string, Set<string>>();
  for (const node of architecture.nodes) if (node.instanceId && node.callId) {
    const group = calls.get(node.instanceId) ?? new Set<string>();
    group.add(node.callId); calls.set(node.instanceId, group);
  }
  return architecture.nodes.map(node => ({
    id: node.id, sourceLabel: node.label, kind: node.kind, category: node.category, evidence: node.evidence,
    ...(node.instanceId ? { instanceId: node.instanceId, callCount: calls.get(node.instanceId)?.size ?? 0 } : {}),
    ...(node.callId ? { callId: node.callId } : {}),
    ...(node.repeat ? { repeat: structuredClone(node.repeat) } : {}),
    ...(node.sourceStructure ? { sourceStructure: true as const } : {}),
    ...(node.outputPath ? { outputPath: structuredClone(node.outputPath) } : {}),
    ...(node.source ? { source: { path: node.source.path, line: node.source.line, endLine: node.source.endLine,
      expression: node.source.expression } } : {}),
  }));
}

/** A compact authored slot label; the inspector and metadata retain the full key. */
export function compactOutputPath(path: OutputPathSegment[]): string {
  return `return${path.map(segment => segment.kind === 'index' ? `[${segment.index}]`
    : typeof segment.key === 'string' && /^[A-Za-z_][A-Za-z0-9_]*$/.test(segment.key) ? `.${segment.key}`
      : `[${JSON.stringify(segment.key)}]`).join('')}`;
}

export function evidenceText(node: ArchitectureNode): string {
  if (node.sourceStructure) return '源码结构查看项：保留条件分支、模块定义和调用表达式；实际执行路径、张量连接和重复次数尚未确定。';
  if (node.evidence === 'opaque' && node.children.length) return '条件路径尚未确定；可以展开查看源码中已有的分支和模块定义。内部查看项不代表已验证的张量流。';
  return node.evidence === 'opaque' ? '未知边界：内部计算尚未恢复，不能从名称推断算子或张量形状。'
    : node.evidence === 'contract' ? '依据已注册的框架合同；没有补画库内部实现。'
      : '依据当前源码恢复；静态证据不证明运行结果或具体张量形状。';
}
