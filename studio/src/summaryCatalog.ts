import { t } from './i18n.ts';
/** Static, pinned Summary assets. Source paths in the IR are provenance only. */
export const SUMMARY_CATALOG_LIMITS = Object.freeze({ bytes: 16_000_000, nodes: 4000, edges: 5000 });
type Asset = { path: string; bytes: number; sha256: string };
export type SummaryCatalogModel = {
  id: string; title: string; nodes: number; edges: number; digest: string;
  runtime: string | null; coverage: string | null; ir: Asset; presentation: Asset | null;
  program?: { id: string; label: string; constructor: Record<string, unknown>; observations: number };
};
export type SummaryCatalog = { schema: 'archcanvas-summary-catalog/1'; models: SummaryCatalogModel[] };
export type SummaryPreviewCase = { id: string; title: string; views: { key: string; label: string; nodes: number; edges: number }[]; runtimeExpansion?: unknown };
const base = '/preview/data/semantic/';
const object = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Summary 目录格式无效。');
  return value as Record<string, unknown>;
};
const count = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0;
const digest = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function asset(value: unknown): Asset {
  const v = object(value);
  if (typeof v.path !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_./-]*\.json$/.test(v.path) || v.path.split('/').some(p => !p || p === '..' || p === '.') || !count(v.bytes) || !digest(v.sha256)) throw Error('Summary 目录资产引用无效。');
  return v as Asset;
}
export function parseSummaryCatalog(value: unknown): SummaryCatalog {
  const v = object(value), limits = object(v.limits);
  if (v.schema !== 'archcanvas-summary-catalog/1' || !Array.isArray(v.models) || v.models.length > 1000 || Object.entries(SUMMARY_CATALOG_LIMITS).some(([key, limit]) => limits[key] !== limit)) throw Error('Summary 目录版本或预算不匹配。');
  const seen = new Set<string>();
  const models = v.models.map(value => {
    const m = object(value);
    if (typeof m.id !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(m.id) || seen.has(m.id) || typeof m.title !== 'string' || !m.title || m.title.length > 240 || !count(m.nodes) || !count(m.edges) || !digest(m.digest) || ![m.runtime,m.coverage].every(x => x === null || typeof x === 'string')) throw Error('Summary 模型身份或计数无效。');
    seen.add(m.id);
    if (m.program !== undefined) {
      const program = object(m.program);
      if (!digest(program.id) || typeof program.label !== 'string' || !program.label || !count(program.observations)) throw Error('Summary 源程序身份无效。');
      object(program.constructor);
    }
    return { ...m, ir: asset(m.ir), presentation: m.presentation === null ? null : asset(m.presentation) } as SummaryCatalogModel;
  });
  return { schema: 'archcanvas-summary-catalog/1', models };
}
/** Constructor variants share an entry only when the entry-source hash agrees. */
export function summaryPrograms(models: SummaryCatalogModel[]) {
  const programs = new Map<string, { id: string; title: string; models: SummaryCatalogModel[] }>();
  for (const model of models) {
    const id = model.program?.id ?? model.id;
    let program = programs.get(id);
    if (!program) { program = { id, title: model.title, models: [] }; programs.set(id, program); }
    program.models.push(model);
    if (program.models.length > 1) program.title = model.program?.label ?? program.title;
  }
  return [...programs.values()];
}
export function summaryConfiguration(model: SummaryCatalogModel) {
  const values = model.program?.constructor ?? {};
  const parameters = Object.entries(values).map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(', ');
  return `${parameters || t('默认构造参数')}${model.program?.observations ? t(' · {0} 条观察记录', {0: model.program.observations}) : ''}`;
}
export function summaryCatalogBlockReason(model: SummaryCatalogModel): string | null {
  if (model.nodes > SUMMARY_CATALOG_LIMITS.nodes || model.edges > SUMMARY_CATALOG_LIMITS.edges) return `原始图 ${model.nodes} 节点 / ${model.edges} 依赖，超过当前 ${SUMMARY_CATALOG_LIMITS.nodes} 节点 / ${SUMMARY_CATALOG_LIMITS.edges} 依赖预算。`;
  if (model.ir.bytes > SUMMARY_CATALOG_LIMITS.bytes || (model.presentation?.bytes ?? 0) > SUMMARY_CATALOG_LIMITS.bytes) return '模型资产超过当前 16 MB 文档预算。';
  return null;
}
async function bytes(url: string, limit: number, signal?: AbortSignal): Promise<Uint8Array<ArrayBuffer>> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw Error(`Summary 资产读取失败（${response.status}）。`);
  if (Number(response.headers.get('Content-Length')) > limit) { await response.body?.cancel(); throw Error('Summary 资产超过读取预算。'); }
  if (!response.body) throw Error('Summary 资产内容为空。');
  const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const next = await reader.read(); if (next.done) break;
      size += next.value.byteLength;
      if (size > limit) { await reader.cancel(); throw Error('Summary 资产超过读取预算。'); }
      chunks.push(next.value);
    }
  } finally { reader.releaseLock(); }
  const result = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return result;
}
export async function loadSummaryCatalog(signal?: AbortSignal): Promise<SummaryCatalog> {
  return parseSummaryCatalog(JSON.parse(new TextDecoder().decode(await bytes(base + 'studio-catalog.json', 512_000, signal))));
}
export async function loadSummaryPreviewCases(signal?: AbortSignal): Promise<SummaryPreviewCase[]> {
  const value = object(JSON.parse(new TextDecoder().decode(await bytes('/preview/data/summary-cases.json', 512_000, signal))));
  if (value.schema !== 'summary-merge/1' || !Array.isArray(value.cases) || value.cases.length > 1000) throw Error('Summary 案例目录无效。');
  const ids = new Set<string>();
  return value.cases.map(raw => {
    const item = object(raw);
    if (typeof item.id !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(item.id) || ids.has(item.id) || typeof item.title !== 'string' || !Array.isArray(item.views) || !item.views.length) throw Error('Summary 案例身份无效。');
    ids.add(item.id);
    for (const rawView of item.views) {
      const view = object(rawView);
      if (typeof view.key !== 'string' || typeof view.label !== 'string' || !count(view.nodes) || !count(view.edges)) throw Error('Summary 案例视图无效。');
    }
    return item as SummaryPreviewCase;
  });
}
async function readAsset(reference: Asset, signal?: AbortSignal) {
  const ref = asset(reference), data = await bytes(base + ref.path, Math.min(ref.bytes, SUMMARY_CATALOG_LIMITS.bytes), signal);
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data))).map(n => n.toString(16).padStart(2,'0')).join('');
  if (data.length !== ref.bytes || hash !== ref.sha256) throw Error('Summary 资产字节或摘要与目录不一致。');
  return object(JSON.parse(new TextDecoder().decode(data)));
}
export async function loadSummaryCatalogModel(model: SummaryCatalogModel, signal?: AbortSignal): Promise<Record<string, unknown>> {
  const reason = summaryCatalogBlockReason(model); if (reason) throw Error(reason);
  const ir = await readAsset(model.ir, signal);
  if (ir.schema !== 'archcanvas-source-semantic/2' || ir.ir_digest !== model.digest || !Array.isArray(ir.nodes) || ir.nodes.length !== model.nodes || !Array.isArray(ir.edges) || ir.edges.length !== model.edges) throw Error('Summary IR 与目录身份或计数不一致。');
  let state: Record<string, unknown> | undefined;
  if (model.presentation) {
    const profile = await readAsset(model.presentation, signal);
    // Same contract as Summary's SemanticPresentationProfile.validate.
    if (profile.schema !== 'semantic-presentation/1' || profile.ir_digest !== ir.ir_digest || typeof profile.revision !== 'string' || !profile.revision) throw Error('展示配置与当前 IR 不匹配。');
    state = object(profile.default_state);
  }
  // D.read validates the complete semantic graph and provides its normal F0
  // when no reviewed initial state exists. Preserve the complete original IR.
  return state ? { schema: 'archcanvas-native-semantic/1', renderer: 'native-semantic/15', ir, state,
    migration: { schema: 'summary-catalog-origin/1', id: model.id, title: model.title, irAssetSha256: model.ir.sha256, presentationAssetSha256: model.presentation?.sha256 } } : ir;
}
