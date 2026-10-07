import type { DraftCatalog, DraftModule } from './authoring.ts';
import type { DraftPreset } from './authoringPresets.ts';

const CATEGORY_LABELS: Readonly<Record<string, string>> = {
  io: '输入与输出', dense: '全连接', activation: '激活函数', operator: '基础算子',
  regularization: '正则化', reshape: '形状变换', convolution: '卷积', pooling: '池化',
  normalization: '归一化', embedding: '嵌入', merge: '合并与分支',
};
// Search aliases describe registered operators; they never create a module or
// imply that two different operations have interchangeable contracts.
const MODULE_ALIASES: Readonly<Record<string, readonly string[]>> = {
  Input: ['输入张量', '输入层', 'tensor input'], Output: ['输出张量', '输出层', 'tensor output'],
  Linear: ['fc', 'fully connected', 'dense', 'affine', '线性层'],
  ReLU: ['rectified linear unit'], GELU: ['gaussian error linear unit'],
  SiLU: ['swish'], Identity: ['直通', '恒等层', 'pass through'],
  Dropout: ['丢弃', '随机失活层'], Flatten: ['flattening', '拉平'],
  Conv2d: ['conv 2d', 'conv2', '2d convolution', '二维卷积层'],
  MaxPool2d: ['max pool', 'max pooling', '最大池化'],
  AdaptiveAvgPool2d: ['adaptive average pool', 'global average pooling', 'gap', '自适应均值池化'],
  BatchNorm2d: ['batch norm', 'batch normalization', 'bn', '批标准化'],
  LayerNorm: ['layer norm', 'layer normalization', 'ln', '层标准化'],
  Embedding: ['embeddings', 'lookup', '词向量', '嵌入层'],
  Add: ['addition', 'sum', '相加', '残差', 'residual', 'skip connection', '跳连'],
  Concat: ['concatenate', 'concatenation', 'cat', '拼接'],
};
const PRESET_ALIASES: Readonly<Record<string, readonly string[]>> = {
  mlp: ['multilayer perceptron', '多层感知机'],
  cnn: ['convolutional neural network', '卷积神经网络', '图像分类'],
  'residual-mlp': ['residual network', '残差网络', 'skip connection', '跳连'],
};
const EXACT_MODULE_NAMES = new Set([
  ...Object.keys(MODULE_ALIASES), 'Sigmoid', 'Tanh', 'Softmax', 'Conv1d', 'AvgPool2d',
  'BatchNorm1d', 'MultiheadAttention', 'Attention', 'LSTM', 'GRU',
].map(kind => kind.toLowerCase()));

export function draftPaletteCategoryLabel(category: string): string { return CATEGORY_LABELS[category] ?? category; }

/** Categories and counts come only from the active runtime catalog. */
export function draftPaletteCategories(catalog: DraftCatalog | null) {
  const counts = new Map<string, number>();
  for (const module of catalog?.modules ?? []) counts.set(module.category, (counts.get(module.category) ?? 0) + 1);
  return [...counts].map(([id, count]) => ({ id, label: draftPaletteCategoryLabel(id), count }));
}

function searchable(value: string): string { return value.normalize('NFKC').toLowerCase(); }
function requestedOperator(query: string): string | null {
  const name = searchable(query).trim().replace(/^nn\./, '');
  return EXACT_MODULE_NAMES.has(name) ? name : null;
}
function matches(value: string, query: string): boolean {
  const text = searchable(value);
  return searchable(query).trim().split(/\s+/).every(term => text.includes(term));
}
function moduleKeywords(module: DraftModule): string {
  return [module.kind, `nn.${module.kind}`, module.label, module.description,
    module.category, draftPaletteCategoryLabel(module.category), ...(MODULE_ALIASES[module.kind] ?? []),
    ...module.parameters.map(parameter => parameter.name)].join(' ');
}

export function draftModuleMatches(module: DraftModule, query: string): boolean {
  // A complete operator name is an exact lookup. Tanh must not become GELU's
  // optional approximation, or AvgPool2d become AdaptiveAvgPool2d by substring.
  const operator = requestedOperator(query);
  return operator ? module.kind.toLowerCase() === operator : matches(moduleKeywords(module), query);
}

/** Search a transparent starting graph by its actual editable module kinds. */
export function draftPresetMatches(preset: DraftPreset, catalog: DraftCatalog | null, query: string): boolean {
  const operator = requestedOperator(query);
  if (operator) return preset.nodes.some(node => node.kind.toLowerCase() === operator);
  const components = preset.nodes.map(node => {
    const module = catalog?.modules.find(item => item.kind === node.kind);
    return module ? moduleKeywords(module) : node.kind;
  });
  return matches([preset.id, preset.label, preset.description, preset.input, preset.output,
    ...(PRESET_ALIASES[preset.id] ?? []), ...components].join(' '), query);
}

export function filterDraftModules(catalog: DraftCatalog | null, query: string, category = ''): DraftModule[] {
  return (catalog?.modules ?? []).filter(module => (!category || module.category === category) && draftModuleMatches(module, query));
}
