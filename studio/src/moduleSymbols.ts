/** Reading aids only. Use semantic operators, never arbitrary display names. */
export type ModuleSymbol = 'module' | 'variable' | 'matrix' | 'add' | 'multiply' | 'hadamard' | 'matmul' | 'activation' | 'linear' | 'norm' | 'attention' | 'reshape' | 'unknown';
export function moduleSymbol(node: { kind?: string; operator?: string; semantic_type?: string; shape?: unknown }): { symbol: ModuleSymbol; description: string } {
  const op = node.operator, type = node.semantic_type;
  if (op === 'add' || type === 'elementwise-add') return { symbol: 'add', description: '相加' };
  if (type === 'elementwise-multiply' || type === 'hadamard-product') return { symbol: 'hadamard', description: '逐元素相乘' };
  if (['matmul', 'bmm', 'mm'].includes(op ?? '')) return { symbol: 'matmul', description: '矩阵乘法' };
  if (['mul', 'mult', 'multiply'].includes(op ?? '')) return { symbol: 'multiply', description: '乘法（不推断广播或矩阵规则）' };
  if (type?.includes('attention')) return { symbol: 'attention', description: '注意力' };
  if (type?.includes('norm') || op === 'normalization' || node.kind === 'normalization') return { symbol: 'norm', description: '归一化' };
  if (type === 'linear' || op === 'linear') return { symbol: 'linear', description: '线性映射' };
  if (type === 'activation' || ['activation', 'tanh', 'relu', 'gelu', 'sigmoid', 'silu', 'softmax'].includes(op ?? '')) return { symbol: 'activation', description: '激活或概率映射' };
  if (['reshape', 'view', 'transpose', 'permute', 'expand'].includes(op ?? '')) return { symbol: 'reshape', description: '形状或维度变换' };
  if (Array.isArray(node.shape) && node.shape.length === 2) return { symbol: 'matrix', description: '二维矩阵' };
  if (['parameter', 'buffer', 'state', 'value-alias', 'interface', 'tensor', 'input', 'output'].includes(node.kind ?? '')) return { symbol: 'variable', description: '变量 / 张量（不推断形状）' };
  if (['composite', 'group', 'container'].includes(node.kind ?? '')) return { symbol: 'module', description: '模块或容器' };
  return { symbol: 'unknown', description: '操作 / 未解析单元' };
}
