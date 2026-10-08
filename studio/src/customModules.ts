import type { DraftModule } from './authoring.ts';
import type { Architecture, OutputPathSegment } from './core/types.ts';

export type CustomModuleDefinition = { schemaVersion: 1; source: string; entry: string; label: string;
  constructorValues: Record<string, unknown>; kind: string; digest: string; sourceDigest: string;
  inputs: { id: string; name: string; positionalOnly: boolean }[];
  outputs: { id: string; name: string; path: OutputPathSegment[] }[] };
export type CustomModulePreview = { definition: CustomModuleDefinition; module: DraftModule; architecture: Architecture; verification: Record<string, unknown> };

export function customModuleCatalog(definition: CustomModuleDefinition): DraftModule {
  return { kind: definition.kind, label: definition.label, category: 'custom',
    description: `${definition.entry} · 自定义源码模块，输出形状未推测`, defaults: {}, parameters: [],
    ports: [...definition.inputs.map(input => ({ id: input.id, name: input.name, direction: 'in' as const, type: 'tensor' as const })),
      ...definition.outputs.map(output => ({ id: output.id, name: output.name, direction: 'out' as const, type: 'tensor' as const }))] };
}
export function readCustomModuleDefinition(value: unknown): CustomModuleDefinition {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('自定义模块定义无效');
  const d = value as CustomModuleDefinition;
  if (d.schemaVersion !== 1 || typeof d.source !== 'string' || !d.source.trim() || d.source.length > 200_000 ||
    typeof d.entry !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(d.entry) || typeof d.label !== 'string' || !d.label || d.label.length > 120 ||
    !/^Custom_[a-f0-9]{24}$/.test(d.kind) || !/^[a-f0-9]{64}$/.test(d.digest) || !/^[a-f0-9]{64}$/.test(d.sourceDigest) ||
    !d.constructorValues || typeof d.constructorValues !== 'object' || Array.isArray(d.constructorValues) ||
    !Array.isArray(d.inputs) || !Array.isArray(d.outputs) || !d.outputs.length || d.inputs.length > 32 || d.outputs.length > 32)
    throw new Error('自定义模块源码/边界合同无效');
  const ids = new Set<string>();
  for (const port of [...d.inputs, ...d.outputs]) {
    if (!port || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(port.id) || typeof port.name !== 'string' || !port.name || ids.has(port.id)) throw new Error('自定义模块端口合同无效');
    ids.add(port.id);
  }
  for (const port of d.inputs) if (typeof port.positionalOnly !== 'boolean') throw new Error('自定义模块输入合同无效');
  for (const port of d.outputs) if (!Array.isArray(port.path) || port.path.some(segment => !segment ||
    !(segment.kind === 'index' && Number.isSafeInteger(segment.index) && segment.index >= 0 ||
      segment.kind === 'key' && (segment.key === null || ['string', 'boolean', 'number'].includes(typeof segment.key))))) throw new Error('自定义模块输出合同无效');
  return structuredClone(d);
}
