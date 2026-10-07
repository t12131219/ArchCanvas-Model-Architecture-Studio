import { connectDraft, draftModuleSize, draftNodeBounds } from './authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftModule, DraftParameter, DraftValue } from './authoring.ts';

type PresetNode = { key: string; kind: string; label: string; parameters?: Record<string, DraftValue>; x: number; y: number };
type PresetEdge = { source: string; target: string; port?: string; sourcePort?: string };
export type DraftPreset = { id: string; label: string; description: string; input: string; output: string; nodes: PresetNode[]; edges: PresetEdge[] };
export type PresetInsertion = { nodeIds: string[]; edgeIds: string[]; inputNodeId: string; position: { x: number; y: number } };

/** Transparent starting graphs: every operator remains a normal editable draft node. */
const originalPresets: readonly DraftPreset[] = [
  { id: 'mlp', label: '最小 MLP', description: '两层全连接与 ReLU', input: 'float32 · [1, 16]', output: '[1, 4]',
    nodes: [
      { key: 'input', kind: 'Input', label: '输入', parameters: { shape: [1, 16], dtype: 'float32' }, x: 0, y: 0 },
      { key: 'hidden', kind: 'Linear', label: '隐藏层', parameters: { in_features: 16, out_features: 32 }, x: 248, y: 0 },
      { key: 'relu', kind: 'ReLU', label: 'ReLU 激活', x: 496, y: 0 },
      { key: 'head', kind: 'Linear', label: '输出层', parameters: { in_features: 32, out_features: 4 }, x: 744, y: 0 },
      { key: 'output', kind: 'Output', label: '输出', x: 992, y: 0 },
    ], edges: [{ source: 'input', target: 'hidden' }, { source: 'hidden', target: 'relu' }, { source: 'relu', target: 'head' }, { source: 'head', target: 'output' }] },
  { id: 'cnn', label: '小型 CNN', description: '卷积、池化与分类头', input: 'float32 · [1, 3, 32, 32]', output: '[1, 4]',
    nodes: [
      { key: 'input', kind: 'Input', label: '图像输入', parameters: { shape: [1, 3, 32, 32], dtype: 'float32' }, x: 0, y: 0 },
      { key: 'conv', kind: 'Conv2d', label: '卷积', parameters: { in_channels: 3, out_channels: 8, kernel_size: [3, 3], stride: [1, 1], padding: [1, 1] }, x: 222, y: 0 },
      { key: 'relu', kind: 'ReLU', label: 'ReLU 激活', x: 444, y: 0 },
      { key: 'pool', kind: 'MaxPool2d', label: '最大池化', parameters: { kernel_size: [2, 2], stride: [2, 2] }, x: 666, y: 0 },
      { key: 'average', kind: 'AdaptiveAvgPool2d', label: '自适应平均池化', parameters: { output_size: [1, 1] }, x: 0, y: 180 },
      { key: 'flatten', kind: 'Flatten', label: '展平', parameters: { start_dim: 1, end_dim: -1 }, x: 222, y: 180 },
      { key: 'head', kind: 'Linear', label: '分类头', parameters: { in_features: 8, out_features: 4 }, x: 444, y: 180 },
      { key: 'output', kind: 'Output', label: '输出', x: 666, y: 180 },
    ], edges: [{ source: 'input', target: 'conv' }, { source: 'conv', target: 'relu' }, { source: 'relu', target: 'pool' }, { source: 'pool', target: 'average' }, { source: 'average', target: 'flatten' }, { source: 'flatten', target: 'head' }, { source: 'head', target: 'output' }] },
  { id: 'residual-mlp', label: '残差 MLP', description: '两层全连接与输入跳连', input: 'float32 · [1, 16]', output: '[1, 16]',
    nodes: [
      { key: 'input', kind: 'Input', label: '输入', parameters: { shape: [1, 16], dtype: 'float32' }, x: 0, y: 0 },
      { key: 'hidden', kind: 'Linear', label: '隐藏层', parameters: { in_features: 16, out_features: 32 }, x: 248, y: 0 },
      { key: 'relu', kind: 'ReLU', label: 'ReLU 激活', x: 496, y: 0 },
      { key: 'projection', kind: 'Linear', label: '投影层', parameters: { in_features: 32, out_features: 16 }, x: 744, y: 0 },
      { key: 'add', kind: 'Add', label: '残差相加', x: 992, y: 0 },
      { key: 'output', kind: 'Output', label: '输出', x: 1240, y: 0 },
    ], edges: [{ source: 'input', target: 'hidden' }, { source: 'hidden', target: 'relu' }, { source: 'relu', target: 'projection' }, { source: 'projection', target: 'add', port: 'left' }, { source: 'input', target: 'add', port: 'right' }, { source: 'add', target: 'output' }] },
];


type ChainPart = { kind: string; label?: string; parameters?: Record<string, DraftValue> };
/** Spatially compact transparent graphs, not opaque whole-network promises. */
function chainPreset(id: string, label: string, description: string, shape: number[], outputShape: number[], parts: ChainPart[], dtype = 'float32'): DraftPreset {
  const nodes: PresetNode[] = [{ key: 'input', kind: 'Input', label: '输入', parameters: { shape, dtype }, x: 0, y: 0 },
    ...parts.map((part, index) => ({ key: `part${index}`, kind: part.kind, label: part.label ?? part.kind, parameters: part.parameters, x: ((index + 1) % 5) * 248, y: Math.floor((index + 1) / 5) * 200 })),
    { key: 'output', kind: 'Output', label: '输出', x: ((parts.length + 1) % 5) * 248, y: Math.floor((parts.length + 1) / 5) * 200 }];
  return { id, label, description, input: `${dtype} · [${shape.join(', ')}]`, output: `[${outputShape.join(', ')}]`, nodes,
    edges: nodes.slice(1).map((node, index) => ({ source: nodes[index].key, target: node.key })) };
}
const additionalPresets: DraftPreset[] = [
  chainPreset('feedforward', 'Transformer 前馈层', 'LayerNorm → Linear → GELU → Dropout → Linear', [2, 8, 16], [2, 8, 16], [
    { kind: 'LayerNorm' }, { kind: 'Linear', parameters: { in_features: 16, out_features: 64 } }, { kind: 'GELU' },
    { kind: 'Dropout' }, { kind: 'Linear', parameters: { in_features: 64, out_features: 16 } }]),
  chainPreset('cnn1d', '一维时序 CNN', 'Conv1d → BatchNorm1d → SiLU → 全局平均池化 → 分类', [2, 3, 64], [2, 4], [
    { kind: 'Conv1d', parameters: { in_channels: 3, out_channels: 16, padding: [1] } }, { kind: 'BatchNorm1d' }, { kind: 'SiLU' },
    { kind: 'AdaptiveAvgPool1d' }, { kind: 'Flatten' }, { kind: 'Linear', parameters: { in_features: 16, out_features: 4 } }]),
  chainPreset('cnn3d', '三维体数据 CNN', 'Conv3d → BatchNorm3d → ReLU → 三维池化 → 分类', [2, 3, 8, 16, 16], [2, 4], [
    { kind: 'Conv3d', parameters: { in_channels: 3, out_channels: 16, padding: [1, 1, 1] } }, { kind: 'BatchNorm3d' }, { kind: 'ReLU' },
    { kind: 'AdaptiveAvgPool3d' }, { kind: 'Flatten' }, { kind: 'Linear', parameters: { in_features: 16, out_features: 4 } }]),
  chainPreset('conv-norm-act', '卷积归一化激活', '可复用 Conv2d → BatchNorm2d → ReLU 图块', [2, 3, 32, 32], [2, 16, 32, 32], [
    { kind: 'Conv2d', parameters: { in_channels: 3, out_channels: 16, padding: [1, 1] } }, { kind: 'BatchNorm2d' }, { kind: 'ReLU' }]),
  chainPreset('depthwise-separable', '深度可分离卷积', '分组深度卷积 → 逐点卷积 → BN → SiLU；MobileNet 常用结构', [2, 16, 32, 32], [2, 32, 32, 32], [
    { kind: 'Conv2d', label: 'Depthwise 卷积', parameters: { in_channels: 16, out_channels: 16, groups: 16, padding: [1, 1] } },
    { kind: 'Conv2d', label: 'Pointwise 卷积', parameters: { in_channels: 16, out_channels: 32, kernel_size: [1, 1] } },
    { kind: 'BatchNorm2d', parameters: { num_features: 32 } }, { kind: 'SiLU' }]),
  chainPreset('bottleneck', '卷积瓶颈', '1×1 降维 → 3×3 → 1×1 扩维；各卷积均为独立节点', [2, 32, 16, 16], [2, 32, 16, 16], [
    { kind: 'Conv2d', parameters: { in_channels: 32, out_channels: 8, kernel_size: [1, 1] } }, { kind: 'ReLU' },
    { kind: 'Conv2d', parameters: { in_channels: 8, out_channels: 8, padding: [1, 1] } }, { kind: 'ReLU' },
    { kind: 'Conv2d', parameters: { in_channels: 8, out_channels: 32, kernel_size: [1, 1] } }]),
  chainPreset('embedding-mlp', '词嵌入与前馈', 'int64 token → Embedding → LayerNorm → Linear；不包含位置编码', [2, 12], [2, 12, 4], [
    { kind: 'Embedding' }, { kind: 'LayerNorm' }, { kind: 'Linear', parameters: { in_features: 16, out_features: 4 } }], 'int64'),
  chainPreset('gru-classifier', 'GRU 序列分类', 'GRU → 序列均值 → Linear；零初态且没有 PackedSequence', [2, 12, 16], [2, 4], [
    { kind: 'GRU' }, { kind: 'Mean', parameters: { dim: 1, keepdim: false } }, { kind: 'Linear', parameters: { in_features: 32, out_features: 4 } }]),
  chainPreset('lstm-classifier', 'LSTM 序列分类', 'LSTM → 序列均值 → Linear；保留可连接的 h_n 与 c_n 端口', [2, 12, 16], [2, 4], [
    { kind: 'LSTM' }, { kind: 'Mean', parameters: { dim: 1, keepdim: false } }, { kind: 'Linear', parameters: { in_features: 32, out_features: 4 } }]),
  chainPreset('bidirectional-rnn', '双向 RNN', '双向 RNN → Linear；序列输出末维包含两个方向', [2, 12, 16], [2, 12, 4], [
    { kind: 'RNN', parameters: { bidirectional: true } }, { kind: 'Linear', parameters: { in_features: 64, out_features: 4 } }]),
  chainPreset('decoder', '卷积上采样解码', 'ConvTranspose2d → ReLU → Conv2d；从 16×16 恢复 32×32', [2, 16, 16, 16], [2, 3, 32, 32], [
    { kind: 'ConvTranspose2d', parameters: { in_channels: 16, out_channels: 8, stride: [2, 2], padding: [1, 1], output_padding: [1, 1] } },
    { kind: 'ReLU' }, { kind: 'Conv2d', parameters: { in_channels: 8, out_channels: 3, padding: [1, 1] } }]),
  chainPreset('autoencoder', '全连接自编码器', '32 → 8 的瓶颈 → 32，透明编码器与解码器', [2, 32], [2, 32], [
    { kind: 'Linear', label: '编码器', parameters: { in_features: 32, out_features: 8 } }, { kind: 'ReLU' },
    { kind: 'Linear', label: '解码器', parameters: { in_features: 8, out_features: 32 } }, { kind: 'Sigmoid' }]),
  chainPreset('patch-embedding', '图像 Patch 嵌入', '步长卷积生成非重叠 patch → 展平空间轴 → 转置为 token 序列', [2, 3, 32, 32], [2, 64, 16], [
    { kind: 'Conv2d', parameters: { in_channels: 3, out_channels: 16, kernel_size: [4, 4], stride: [4, 4] } },
    { kind: 'Flatten', parameters: { start_dim: 2, end_dim: -1 } }, { kind: 'Transpose', parameters: { dim0: 1, dim1: 2 } }]),
  { id: 'self-attention', label: '自注意力', description: '同一序列连接 Q/K/V；平均权重是独立可连接输出', input: 'float32 · [2, 8, 16]', output: '[2, 8, 16]',
    nodes: [{ key: 'input', kind: 'Input', label: '序列输入', parameters: { shape: [2, 8, 16] }, x: 0, y: 0 },
      { key: 'attn', kind: 'MultiheadAttention', label: '自注意力', x: 248, y: 0 },
      { key: 'output', kind: 'Output', label: '输出', x: 496, y: 0 }],
    edges: ['query', 'key', 'value'].map(port => ({ source: 'input', target: 'attn', port })).concat([{ source: 'attn', target: 'output', port: 'input' }]) },
  { id: 'residual-cnn', label: '卷积残差块', description: '两个 3×3 卷积与 BN，再与原输入相加', input: 'float32 · [2, 16, 32, 32]', output: '[2, 16, 32, 32]',
    nodes: [{ key: 'input', kind: 'Input', label: '输入', parameters: { shape: [2, 16, 32, 32] }, x: 0, y: 0 },
      { key: 'conv1', kind: 'Conv2d', label: '卷积 1', parameters: { in_channels: 16, out_channels: 16, padding: [1, 1] }, x: 248, y: 0 },
      { key: 'bn1', kind: 'BatchNorm2d', label: 'BN 1', x: 496, y: 0 }, { key: 'relu', kind: 'ReLU', label: 'ReLU', x: 744, y: 0 },
      { key: 'conv2', kind: 'Conv2d', label: '卷积 2', parameters: { in_channels: 16, out_channels: 16, padding: [1, 1] }, x: 248, y: 200 },
      { key: 'bn2', kind: 'BatchNorm2d', label: 'BN 2', x: 496, y: 200 }, { key: 'add', kind: 'Add', label: '残差相加', x: 744, y: 200 },
      { key: 'output', kind: 'Output', label: '输出', x: 992, y: 200 }],
    edges: [{ source: 'input', target: 'conv1' }, { source: 'conv1', target: 'bn1' }, { source: 'bn1', target: 'relu' },
      { source: 'relu', target: 'conv2' }, { source: 'conv2', target: 'bn2' }, { source: 'bn2', target: 'add', port: 'left' },
      { source: 'input', target: 'add', port: 'right' }, { source: 'add', target: 'output' }] },
  { id: 'gated-mlp', label: '门控 MLP', description: '两条 Linear 支路，Sigmoid 门逐元素调制内容支路', input: 'float32 · [2, 16]', output: '[2, 32]',
    nodes: [{ key: 'input', kind: 'Input', label: '输入', parameters: { shape: [2, 16] }, x: 0, y: 100 },
      { key: 'content', kind: 'Linear', label: '内容投影', x: 248, y: 0 }, { key: 'gate', kind: 'Linear', label: '门投影', x: 248, y: 200 },
      { key: 'sigmoid', kind: 'Sigmoid', label: '门激活', x: 496, y: 200 }, { key: 'mul', kind: 'Multiply', label: '逐元素门控', x: 744, y: 100 },
      { key: 'output', kind: 'Output', label: '输出', x: 992, y: 100 }],
    edges: [{ source: 'input', target: 'content' }, { source: 'input', target: 'gate' }, { source: 'gate', target: 'sigmoid' },
      { source: 'content', target: 'mul', port: 'left' }, { source: 'sigmoid', target: 'mul', port: 'right' }, { source: 'mul', target: 'output' }] },
];
// One pre-norm encoder block, explicitly decomposed into its editable operators.
const encoder = chainPreset('transformer-block', 'Transformer 编码器块', 'Pre-LN 自注意力与前馈双残差；无位置编码、掩码或缓存', [2, 8, 16], [2, 8, 16], [
  { kind: 'LayerNorm' }, { kind: 'MultiheadAttention' }, { kind: 'Add', label: '注意力残差' }, { kind: 'LayerNorm' },
  { kind: 'Linear', parameters: { in_features: 16, out_features: 64 } }, { kind: 'GELU' }, { kind: 'Dropout' },
  { kind: 'Linear', parameters: { in_features: 64, out_features: 16 } }, { kind: 'Add', label: '前馈残差' }]);
encoder.edges = [{ source: 'input', target: 'part0' }, ...['query', 'key', 'value'].map(port => ({ source: 'part0', target: 'part1', port })),
  { source: 'part1', target: 'part2', port: 'left' }, { source: 'input', target: 'part2', port: 'right' },
  { source: 'part2', target: 'part3' }, { source: 'part3', target: 'part4' }, { source: 'part4', target: 'part5' },
  { source: 'part5', target: 'part6' }, { source: 'part6', target: 'part7' }, { source: 'part7', target: 'part8', port: 'left' },
  { source: 'part2', target: 'part8', port: 'right' }, { source: 'part8', target: 'output' }];
additionalPresets.push(
  { id: 'cross-attention', label: '跨注意力', description: '查询与独立记忆序列连接 Q 与 K/V，可用于编码器—解码器交互', input: 'float32 · Q [2, 6, 16] / KV [2, 10, 16]', output: '[2, 6, 16]',
    nodes: [{ key: 'input', kind: 'Input', label: '查询序列', parameters: { shape: [2, 6, 16] }, x: 0, y: 0 },
      { key: 'memory', kind: 'Input', label: '记忆序列', parameters: { shape: [2, 10, 16] }, x: 0, y: 200 },
      { key: 'attn', kind: 'MultiheadAttention', label: '跨注意力', x: 248, y: 100 },
      { key: 'output', kind: 'Output', label: '输出', x: 496, y: 100 }],
    edges: [{ source: 'input', target: 'attn', port: 'query' }, { source: 'memory', target: 'attn', port: 'key' },
      { source: 'memory', target: 'attn', port: 'value' }, { source: 'attn', target: 'output' }] },
  { id: 'unet-skip', label: 'U-Net 跳连图块', description: '下采样 → 卷积 → 上采样 → 与高分辨率支路拼接；这是单级图块', input: 'float32 · [2, 3, 32, 32]', output: '[2, 4, 32, 32]',
    nodes: [{ key: 'input', kind: 'Input', label: '输入', parameters: { shape: [2, 3, 32, 32] }, x: 0, y: 0 },
      { key: 'skip', kind: 'Conv2d', label: '高分辨率特征', parameters: { in_channels: 3, out_channels: 8, padding: [1, 1] }, x: 248, y: 0 },
      { key: 'pool', kind: 'MaxPool2d', label: '下采样', x: 496, y: 0 },
      { key: 'low', kind: 'Conv2d', label: '低分辨率特征', parameters: { in_channels: 8, out_channels: 16, padding: [1, 1] }, x: 744, y: 0 },
      { key: 'up', kind: 'Upsample', label: '上采样', parameters: { size: [32, 32] }, x: 248, y: 200 },
      { key: 'cat', kind: 'Concat', label: '特征拼接', parameters: { dim: 1 }, x: 496, y: 200 },
      { key: 'head', kind: 'Conv2d', label: '输出投影', parameters: { in_channels: 24, out_channels: 4, kernel_size: [1, 1] }, x: 744, y: 200 },
      { key: 'output', kind: 'Output', label: '输出', x: 992, y: 200 }],
    edges: [{ source: 'input', target: 'skip' }, { source: 'skip', target: 'pool' }, { source: 'pool', target: 'low' },
      { source: 'low', target: 'up' }, { source: 'up', target: 'cat', port: 'a' }, { source: 'skip', target: 'cat', port: 'b' },
      { source: 'cat', target: 'head' }, { source: 'head', target: 'output' }] },
  { id: 'residual-projection', label: '带投影残差块', description: '主路 3×3 步长卷积与跳路 1×1 投影同时下采样，再相加', input: 'float32 · [2, 16, 32, 32]', output: '[2, 32, 16, 16]',
    nodes: [{ key: 'input', kind: 'Input', label: '输入', parameters: { shape: [2, 16, 32, 32] }, x: 0, y: 100 },
      { key: 'main', kind: 'Conv2d', label: '主路卷积', parameters: { in_channels: 16, out_channels: 32, stride: [2, 2], padding: [1, 1] }, x: 248, y: 0 },
      { key: 'bn', kind: 'BatchNorm2d', label: 'BN', parameters: { num_features: 32 }, x: 496, y: 0 },
      { key: 'skip', kind: 'Conv2d', label: '跳路投影', parameters: { in_channels: 16, out_channels: 32, kernel_size: [1, 1], stride: [2, 2] }, x: 248, y: 200 },
      { key: 'add', kind: 'Add', label: '投影相加', x: 744, y: 100 },
      { key: 'output', kind: 'Output', label: '输出', x: 992, y: 100 }],
    edges: [{ source: 'input', target: 'main' }, { source: 'main', target: 'bn' }, { source: 'input', target: 'skip' },
      { source: 'bn', target: 'add', port: 'left' }, { source: 'skip', target: 'add', port: 'right' }, { source: 'add', target: 'output' }] },
);
additionalPresets.push(encoder);
// The first three IDs/layouts are retained for saved palettes and existing trials.
export const draftPresets: readonly DraftPreset[] = [...originalPresets, ...additionalPresets];

function validValue(value: DraftValue | undefined, field: DraftParameter) {
  if (field.type === 'boolean') return typeof value === 'boolean';
  if (field.type === 'choice') return typeof value === 'string' && !!field.options?.includes(value);
  const values = field.type === 'integer-array' ? value : [value];
  if (!Array.isArray(values) || !values.length || values.some(item => typeof item !== 'number' || !Number.isFinite(item) || (field.type !== 'number' && !Number.isInteger(item)) || (field.min !== undefined && item < field.min) || (field.max !== undefined && item > field.max))) return false;
  return field.type !== 'integer-array' || ((field.length === undefined || values.length === field.length) && (field.minLength === undefined || values.length >= field.minLength) && (field.maxLength === undefined || values.length <= field.maxLength));
}
function presetModule(catalog: DraftCatalog, node: PresetNode): DraftModule {
  const modules = catalog.modules.filter(module => module.kind === node.kind);
  if (modules.length !== 1) throw new Error(`当前模块库缺少可用的 ${node.kind}。`);
  const module = modules[0], fields = new Set(module.parameters.map(field => field.name));
  if (fields.size !== module.parameters.length || Object.keys(module.defaults).some(key => !fields.has(key)) || Object.keys(node.parameters ?? {}).some(key => !fields.has(key))) throw new Error(`${node.kind} 的参数表与此网络起点不兼容。`);
  for (const field of module.parameters) if (!validValue(module.defaults[field.name], field) || !validValue(node.parameters?.[field.name] ?? module.defaults[field.name], field)) throw new Error(`${node.kind} 的 ${field.name} 参数与此网络起点不兼容。`);
  const expected = node.kind === 'Input' ? ['output:out'] : node.kind === 'Output' ? ['input:in'] : ['Add', 'Subtract', 'Multiply', 'Divide', 'MatMul'].includes(node.kind) ? ['left:in', 'right:in', 'output:out'] : node.kind === 'Concat' ? ['a:in', 'b:in', 'output:out'] : node.kind === 'MultiheadAttention' ? ['query:in', 'key:in', 'value:in', 'output:out', 'weights:out'] : node.kind === 'LSTM' ? ['input:in', 'output:out', 'h_n:out', 'c_n:out'] : ['RNN', 'GRU'].includes(node.kind) ? ['input:in', 'output:out', 'h_n:out'] : ['input:in', 'output:out'];
  if (module.ports.some(port => port.type !== 'tensor') || JSON.stringify(module.ports.map(port => `${port.id}:${port.direction}`).sort()) !== JSON.stringify(expected.sort())) throw new Error(`${node.kind} 的端口与此网络起点不兼容。`);
  return module;
}
export function draftPresetUnavailable(preset: DraftPreset, catalog: DraftCatalog | null): string | null {
  if (!catalog) return '正在加载模块库。';
  if (catalog.schemaVersion !== 1 || catalog.mode !== 'authored-draft') return '当前模块库不支持这些网络起点。';
  try { preset.nodes.forEach(node => presetModule(catalog, node)); return null; }
  catch (reason) { return reason instanceof Error ? reason.message : String(reason); }
}
export function draftPresetSize(preset: DraftPreset, catalog: DraftCatalog) {
  const boxes = preset.nodes.map(node => ({ x: node.x, y: node.y, ...draftModuleSize(presetModule(catalog, node)) }));
  return { width: Math.max(...boxes.map(box => box.x + box.width)), height: Math.max(...boxes.map(box => box.y + box.height)) };
}

/** Stage the whole independent graph before publishing one draft-history change. */
export function insertDraftPreset(draft: AuthoredDraft, catalog: DraftCatalog, presetId: string, preferred: { x: number; y: number }, makeId: (prefix: 'n' | 'e') => string = prefix => `${prefix}_${crypto.randomUUID().replaceAll('-', '')}`): PresetInsertion {
  const preset = draftPresets.find(item => item.id === presetId);
  if (!preset) throw new Error('未找到此网络起点。');
  const unavailable = draftPresetUnavailable(preset, catalog); if (unavailable) throw new Error(unavailable);
  if (draft.nodes.length + preset.nodes.length > 128 || draft.edges.length + preset.edges.length > 384) throw new Error('空间不足：草稿最多允许 128 个模块、384 条连接。');
  if (!Number.isFinite(preferred.x) || !Number.isFinite(preferred.y) || Math.abs(preferred.x) > 1_000_000 || Math.abs(preferred.y) > 1_000_000) throw new Error('请在有效画布位置添加网络。');
  const { width, height } = draftPresetSize(preset, catalog);
  let position = { x: Math.round(preferred.x), y: Math.round(preferred.y) };
  // Move the entire network below intersecting old cards; old objects never move.
  while (true) {
    const overlaps = draft.nodes.map(node => draftNodeBounds(node, catalog)).filter(box => box.x < position.x + width + 20 && box.x + box.width + 20 > position.x && box.y < position.y + height + 20 && box.y + box.height + 20 > position.y);
    if (!overlaps.length) break;
    position = { x: position.x, y: Math.max(...overlaps.map(box => box.y + box.height + 28)) };
  }
  if (Math.abs(position.x) > 1_000_000 || Math.abs(position.y) > 1_000_000 || preset.nodes.some(node => Math.abs(position.x + node.x) > 1_000_000 || Math.abs(position.y + node.y) > 1_000_000)) throw new Error('此位置没有足够空间；请平移画布后重试。');
  const used = new Set([...draft.nodes.map(node => node.id), ...draft.edges.map(edge => edge.id)]);
  function identity(prefix: 'n' | 'e') {
    for (let attempt = 0; attempt < 64; attempt++) {
      const id = makeId(prefix);
      if (typeof id === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(id) && !used.has(id)) { used.add(id); return id; }
    }
    throw new Error('无法分配新模块标识；原草稿已保留，请重试。');
  }
  const candidate = structuredClone(draft), byKey = new Map<string, string>();
  const nodeIds = preset.nodes.map(node => {
    const id = identity('n'), module = presetModule(catalog, node); byKey.set(node.key, id);
    candidate.nodes.push({ id, kind: node.kind, label: node.label, parameters: { ...structuredClone(module.defaults), ...structuredClone(node.parameters ?? {}) }, position: { x: position.x + node.x, y: position.y + node.y } });
    return id;
  });
  const edgeIds = preset.edges.map(edge => {
    const id = identity('e');
    connectDraft(candidate, catalog, { nodeId: byKey.get(edge.source)!, portId: edge.sourcePort ?? 'output' }, { nodeId: byKey.get(edge.target)!, portId: edge.port ?? 'input' }, id);
    return id;
  });
  draft.nodes = candidate.nodes; draft.edges = candidate.edges;
  return { nodeIds, edgeIds, inputNodeId: byKey.get('input')!, position };
}
