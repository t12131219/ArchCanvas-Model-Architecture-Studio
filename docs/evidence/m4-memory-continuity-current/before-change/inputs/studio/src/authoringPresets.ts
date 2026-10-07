import { connectDraft, draftModuleSize, draftNodeBounds } from './authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftModule, DraftParameter, DraftValue } from './authoring.ts';

type PresetNode = { key: string; kind: string; label: string; parameters?: Record<string, DraftValue>; x: number; y: number };
type PresetEdge = { source: string; target: string; port?: string };
export type DraftPreset = { id: string; label: string; description: string; input: string; output: string; nodes: PresetNode[]; edges: PresetEdge[] };
export type PresetInsertion = { nodeIds: string[]; edgeIds: string[]; inputNodeId: string; position: { x: number; y: number } };

/** Transparent starting graphs: every operator remains a normal editable draft node. */
export const draftPresets: readonly DraftPreset[] = [
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
      { key: 'conv', kind: 'Conv2d', label: '卷积', parameters: { in_channels: 3, out_channels: 8, kernel_size: [3, 3], stride: [1, 1], padding: [1, 1] }, x: 224, y: 0 },
      { key: 'relu', kind: 'ReLU', label: 'ReLU 激活', x: 448, y: 0 },
      { key: 'pool', kind: 'MaxPool2d', label: '最大池化', parameters: { kernel_size: [2, 2], stride: [2, 2] }, x: 672, y: 0 },
      { key: 'average', kind: 'AdaptiveAvgPool2d', label: '自适应平均池化', parameters: { output_size: [1, 1] }, x: 0, y: 180 },
      { key: 'flatten', kind: 'Flatten', label: '展平', parameters: { start_dim: 1, end_dim: -1 }, x: 224, y: 180 },
      { key: 'head', kind: 'Linear', label: '分类头', parameters: { in_features: 8, out_features: 4 }, x: 448, y: 180 },
      { key: 'output', kind: 'Output', label: '输出', x: 672, y: 180 },
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
  const expected = node.kind === 'Input' ? ['output:out'] : node.kind === 'Output' ? ['input:in'] : node.kind === 'Add' ? ['left:in', 'right:in', 'output:out'] : ['input:in', 'output:out'];
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
    connectDraft(candidate, catalog, { nodeId: byKey.get(edge.source)!, portId: 'output' }, { nodeId: byKey.get(edge.target)!, portId: edge.port ?? 'input' }, id);
    return id;
  });
  draft.nodes = candidate.nodes; draft.edges = candidate.edges;
  return { nodeIds, edgeIds, inputNodeId: byKey.get('input')!, position };
}
