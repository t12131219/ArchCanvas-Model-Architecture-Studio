import type { Architecture, CanvasDocument, Glyph } from './types.ts';

export class ValidationError extends Error { constructor(message: string) { super(message); this.name = 'ValidationError'; } }
export const GLYPHS: Glyph[] = ['module', 'operator', 'tensor', 'add', 'attention', 'norm', 'opaque'];
type Obj = Record<string, unknown>;
export function object(value: unknown, path: string): Obj {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ValidationError(`${path}: expected object`);
  return value as Obj;
}
export function fields(value: Obj, allowed: string[], path: string) {
  for (const key of Object.keys(value)) if (!allowed.includes(key)) throw new ValidationError(`${path}.${key}: unsupported field`);
}
export function textValue(value: unknown, path: string): string {
  if (typeof value !== 'string') throw new ValidationError(`${path}: expected string`);
  return value;
}
export function finite(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new ValidationError(`${path}: expected finite number`);
  return value;
}
function array(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) throw new ValidationError(`${path}: expected array`);
  return value;
}
function member(value: unknown, choices: string[], path: string) {
  if (!choices.includes(textValue(value, path))) throw new ValidationError(`${path}: unsupported value`);
}
export function color(value: unknown, path: string) {
  if (!/^#[0-9a-f]{3}(?:[0-9a-f]{3})?(?:[0-9a-f]{2})?$/i.test(textValue(value, path))) throw new ValidationError(`${path}: use a hexadecimal color`);
}
function strings(value: unknown, path: string): string[] { return array(value, path).map((v, i) => textValue(v, `${path}[${i}]`)); }
function unique(values: string[], path: string) {
  if (new Set(values).size !== values.length) throw new ValidationError(`${path}: duplicate identity`);
}
export function validateArchitecture(value: unknown): Architecture {
  const a = object(value, 'architecture');
  fields(a, ['schemaVersion', 'id', 'label', 'sourceDigest', 'irDigest', 'entry', 'nodes', 'edges', 'sourceRelations', 'diagnostics', 'sources'], 'architecture');
  if (a.schemaVersion !== 1) throw new ValidationError('architecture.schemaVersion: unsupported version');
  for (const k of ['id', 'label', 'sourceDigest', 'irDigest', 'entry']) textValue(a[k], `architecture.${k}`);
  const nodes = array(a.nodes, 'architecture.nodes').map((v, i) => {
    const n = object(v, `nodes[${i}]`);
    fields(n, ['id', 'label', 'kind', 'category', 'parentId', 'children', 'ports', 'parameters', 'parameterOrigins', 'source', 'evidence', 'repeat', 'instanceId', 'callId', 'outputPath', 'sourceStructure'], 'node');
    for (const k of ['id', 'label', 'kind', 'category']) textValue(n[k], `node.${k}`);
    for (const k of ['parentId', 'instanceId', 'callId']) if (n[k] !== undefined) textValue(n[k], `node.${k}`);
    unique(strings(n.children, 'node.children'), 'node.children');
    object(n.parameters, 'node.parameters');
    if (n.parameterOrigins !== undefined) for (const [parameter, raw] of Object.entries(object(n.parameterOrigins, 'node.parameterOrigins'))) {
      if (!(parameter in (n.parameters as Obj))) throw new ValidationError('parameter origin has no effective value');
      const origin = object(raw, 'parameterOrigin');
      fields(origin, ['kind', 'path', 'line', 'endLine', 'column', 'endColumn', 'expression'], 'parameterOrigin');
      member(origin.kind, ['literal', 'constructor_argument', 'derived', 'unknown'], 'parameterOrigin.kind');
      textValue(origin.path, 'parameterOrigin.path'); textValue(origin.expression, 'parameterOrigin.expression');
      const line = finite(origin.line, 'origin.line'), end = finite(origin.endLine, 'origin.endLine');
      const column = finite(origin.column, 'origin.column'), endColumn = finite(origin.endColumn, 'origin.endColumn');
      if (![line, end, column, endColumn].every(Number.isInteger) || line < 1 || end < line || column < 0 || endColumn < 0 || (line === end && endColumn < column)) throw new ValidationError('parameterOrigin: invalid UTF-8 span');
    }
    member(n.evidence, ['source', 'contract', 'opaque'], 'node.evidence');
    if (n.sourceStructure !== undefined && (n.sourceStructure !== true || n.evidence !== 'source' || !n.source || !String(n.kind).startsWith('Source') || array(n.ports, 'node.ports').length || n.instanceId !== undefined || n.callId !== undefined || n.repeat !== undefined || n.outputPath !== undefined || n.parameterOrigins !== undefined))
      throw new ValidationError('sourceStructure: source inspection cannot declare tensor ports, instances or semantic parameter edits');
    if (n.outputPath !== undefined) {
      if (n.kind !== 'Output' || n.category !== 'output') throw new ValidationError('node.outputPath: only graph Output nodes can declare a return slot');
      for (const value of array(n.outputPath, 'node.outputPath')) {
        const segment = object(value, 'outputPath segment');
        member(segment.kind, ['key', 'index'], 'outputPath.kind');
        if (segment.kind === 'index') {
          fields(segment, ['kind', 'index'], 'outputPath');
          if (!Number.isSafeInteger(finite(segment.index, 'outputPath.index')) || Number(segment.index) < 0) throw new ValidationError('outputPath.index: nonnegative safe integer required');
        } else {
          fields(segment, ['kind', 'key'], 'outputPath');
          const key = segment.key;
          if (key !== null && !['string', 'boolean', 'number'].includes(typeof key)) throw new ValidationError('outputPath.key: finite JSON scalar required');
          if (typeof key === 'number' && (!Number.isFinite(key) || Number.isInteger(key) && !Number.isSafeInteger(key))) throw new ValidationError('outputPath.key: portable finite JSON scalar required');
        }
      }
    }
    const ports = array(n.ports, 'node.ports').map(pv => {
      const p = object(pv, 'port');
      fields(p, ['id', 'name', 'direction', 'role', 'ordinal'], 'port');
      for (const k of ['id', 'name', 'role']) textValue(p[k], `port.${k}`);
      member(p.direction, ['in', 'out'], 'port.direction');
      if (!Number.isInteger(finite(p.ordinal, 'port.ordinal')) || Number(p.ordinal) < 0) throw new ValidationError('port.ordinal: non-negative integer required');
      return p;
    });
    unique(ports.map(p => p.id as string), 'node.ports');
    if (n.source !== undefined) {
      const s = object(n.source, 'node.source');
      fields(s, ['path', 'line', 'endLine', 'expression'], 'node.source');
      textValue(s.path, 'source.path'); textValue(s.expression, 'source.expression');
      const line = finite(s.line, 'source.line'), end = finite(s.endLine, 'source.endLine');
      if (!Number.isInteger(line) || !Number.isInteger(end) || line < 1 || end < line) throw new ValidationError('source: invalid line interval');
    }
    if (n.repeat !== undefined) {
      const r = object(n.repeat, 'node.repeat'); fields(r, ['count', 'sharing'], 'node.repeat');
      if (!Number.isInteger(finite(r.count, 'repeat.count')) || Number(r.count) < 1) throw new ValidationError('repeat.count: positive integer required');
      member(r.sharing, ['independent', 'shared'], 'repeat.sharing');
    }
    return n;
  });
  unique(nodes.map(n => n.id as string), 'architecture.nodes');
  const byId = new Map(nodes.map(n => [n.id as string, n]));
  for (const n of nodes) {
    if (n.parentId !== undefined && !byId.has(n.parentId as string)) throw new ValidationError(`node ${n.id}: missing parent`);
    for (const id of n.children as string[]) if (byId.get(id)?.parentId !== n.id) throw new ValidationError(`node ${n.id}: inconsistent containment ${id}`);
    if (n.parentId !== undefined && !(byId.get(n.parentId as string)!.children as string[]).includes(n.id as string)) throw new ValidationError(`node ${n.id}: missing reciprocal containment`);
    const seen = new Set<string>([n.id as string]);
    let parent = n.parentId as string | undefined;
    while (parent) { if (seen.has(parent)) throw new ValidationError('architecture: containment cycle'); seen.add(parent); parent = byId.get(parent)?.parentId as string | undefined; }
  }
  const edges = array(a.edges, 'architecture.edges').map(v => {
    const e = object(v, 'edge'); fields(e, ['id', 'source', 'target', 'tensorId', 'role', 'label'], 'edge');
    for (const k of ['id', 'tensorId']) textValue(e[k], `edge.${k}`);
    if (e.label !== undefined) textValue(e.label, 'edge.label');
    member(e.role, ['data', 'residual', 'memory', 'mask'], 'edge.role');
    for (const end of ['source', 'target']) {
      const p = object(e[end], `edge.${end}`); fields(p, ['nodeId', 'portId'], `edge.${end}`);
      textValue(p.nodeId, 'binding.nodeId'); textValue(p.portId, 'binding.portId');
      const port = (byId.get(p.nodeId as string)?.ports as Obj[] | undefined)?.find(q => q.id === p.portId);
      if (!port || port.direction !== (end === 'source' ? 'out' : 'in')) throw new ValidationError(`edge ${e.id}: invalid ${end} port binding`);
    }
    return e;
  });
  unique(edges.map(e => e.id as string), 'architecture.edges');
  if (a.sourceRelations !== undefined) {
    const sourceRelations = array(a.sourceRelations, 'architecture.sourceRelations');
    if (sourceRelations.length > 1440) throw new ValidationError('architecture.sourceRelations: exceeds 1440 relation budget');
    const relations = sourceRelations.map(value => {
      const relation = object(value, 'sourceRelation');
      fields(relation, ['id', 'sourceId', 'targetId', 'kind', 'source', 'boundary'], 'sourceRelation');
      for (const key of ['id', 'sourceId', 'targetId']) textValue(relation[key], `sourceRelation.${key}`);
      member(relation.kind, ['value-dependency', 'boundary-dependency'], 'sourceRelation.kind');
      if (relation.sourceId === relation.targetId || ![relation.sourceId, relation.targetId].every(id => byId.has(id as string)))
        throw new ValidationError('sourceRelation: distinct existing endpoints required');
      if (relation.kind === 'value-dependency') {
        if (relation.boundary !== undefined || ![relation.sourceId, relation.targetId].every(id => byId.get(id as string)?.sourceStructure === true))
          throw new ValidationError('sourceRelation: internal arrows require source inspection endpoints');
      } else {
        const boundary = object(relation.boundary, 'sourceRelation.boundary');
        fields(boundary, ['nodeIds', 'edgeIds', 'complete'], 'sourceRelation.boundary');
        const nodeIds = array(boundary.nodeIds, 'sourceRelation.boundary.nodeIds').map(id => textValue(id, 'sourceRelation.boundary.nodeId'));
        const edgeIds = array(boundary.edgeIds, 'sourceRelation.boundary.edgeIds').map(id => textValue(id, 'sourceRelation.boundary.edgeId'));
        unique(nodeIds, 'sourceRelation.boundary.nodeIds'); unique(edgeIds, 'sourceRelation.boundary.edgeIds');
        if (!nodeIds.length || !edgeIds.length || typeof boundary.complete !== 'boolean' || nodeIds.some(id => byId.get(id)?.kind !== 'ConditionalRegion' || byId.get(id)?.sourceStructure === true))
          throw new ValidationError('sourceRelation: canonical conditional boundaries required');
        const bindings = edgeIds.map(id => edges.find(edge => edge.id === id));
        if (bindings.some(edge => !edge || ![edge.source, edge.target].some(end => nodeIds.includes((end as Obj).nodeId as string))) ||
            nodeIds.some(id => !bindings.some(edge => [edge!.source, edge!.target].some(end => (end as Obj).nodeId === id))))
          throw new ValidationError('sourceRelation: boundary edges must reference their canonical boundaries');
        const peers = new Set(bindings.flatMap(edge => [edge!.source, edge!.target].map(end => (end as Obj).nodeId)));
        for (const endpoint of [relation.sourceId, relation.targetId]) {
          let node = byId.get(endpoint as string);
          const inspection = node?.sourceStructure === true;
          while (node && !nodeIds.includes(node.id as string)) node = byId.get(node.parentId as string);
          if (!(inspection && node) && !peers.has(endpoint)) throw new ValidationError('sourceRelation: endpoint has no boundary binding or inspected ancestry');
        }
      }
      const source = object(relation.source, 'sourceRelation.source');
      fields(source, ['path', 'line', 'endLine', 'expression'], 'sourceRelation.source');
      textValue(source.path, 'sourceRelation.source.path'); textValue(source.expression, 'sourceRelation.source.expression');
      const line = finite(source.line, 'sourceRelation.source.line'), end = finite(source.endLine, 'sourceRelation.source.endLine');
      if (!Number.isInteger(line) || !Number.isInteger(end) || line < 1 || end < line) throw new ValidationError('sourceRelation: invalid source interval');
      return relation;
    });
    unique(relations.map(relation => relation.id as string), 'architecture.sourceRelations');
  }
  for (const v of array(a.diagnostics, 'architecture.diagnostics')) { const d = object(v, 'diagnostic'); fields(d, ['level', 'message'], 'diagnostic'); textValue(d.level, 'diagnostic.level'); textValue(d.message, 'diagnostic.message'); }
  for (const v of array(a.sources, 'architecture.sources')) { const s = object(v, 'source'); fields(s, ['path', 'content', 'digest'], 'source'); for (const k of ['path', 'content', 'digest']) textValue(s[k], `source.${k}`); }
  return value as Architecture;
}

export function validateDocument(value: unknown): CanvasDocument {
  const d = object(value, 'document');
  fields(d, ['schemaVersion', 'id', 'title', 'revision', 'sourceBindingDigest', 'architecture', 'displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'portLayoutOverrides', 'legendItems', 'annotations', 'pageSpec', 'expandedIds', 'layout', 'layoutByFrontier', 'pinnedObjects'], 'document');
  if (d.schemaVersion !== 1) throw new ValidationError('document.schemaVersion: unsupported version');
  for (const k of ['id', 'title', 'sourceBindingDigest']) textValue(d[k], `document.${k}`);
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(d.id as string)) throw new ValidationError('document.id: use a safe persistent identity');
  if (!Number.isInteger(finite(d.revision, 'document.revision')) || Number(d.revision) < 0) throw new ValidationError('document.revision: non-negative integer required');
  const a = validateArchitecture(d.architecture), nodeIds = new Set(a.nodes.map(n => n.id)), edgeIds = new Set(a.edges.map(e => e.id));
  if (d.sourceBindingDigest !== a.sourceDigest) throw new ValidationError('document: source binding digest differs from architecture');
  function reference(id: string, ids: Set<string>, path: string) { if (!ids.has(id)) throw new ValidationError(`${path}: unknown object ${id}`); }
  for (const [id, alias] of Object.entries(object(d.displayAliases, 'displayAliases'))) { reference(id, nodeIds, 'displayAliases'); textValue(alias, 'displayAliases.label'); }
  for (const [id, sv] of Object.entries(object(d.nodeStyleOverrides, 'nodeStyleOverrides'))) {
    reference(id, nodeIds, 'nodeStyleOverrides'); const s = object(sv, 'nodeStyle'); fields(s, ['fill', 'stroke', 'glyph'], 'nodeStyle');
    for (const k of ['fill', 'stroke']) if (s[k] !== undefined) color(s[k], `nodeStyle.${k}`);
    if (s.glyph !== undefined) member(s.glyph, GLYPHS, 'nodeStyle.glyph');
  }
  for (const [id, sv] of Object.entries(object(d.edgeStyleOverrides, 'edgeStyleOverrides'))) {
    reference(id, edgeIds, 'edgeStyleOverrides'); const s = object(sv, 'edgeStyle'); fields(s, ['stroke', 'width', 'dashed'], 'edgeStyle');
    if (s.stroke !== undefined) color(s.stroke, 'edgeStyle.stroke');
    if (s.width !== undefined && (finite(s.width, 'edgeStyle.width') < 0.25 || Number(s.width) > 12)) throw new ValidationError('edgeStyle.width: outside supported interval');
    if (s.dashed !== undefined && typeof s.dashed !== 'boolean') throw new ValidationError('edgeStyle.dashed: expected boolean');
  }
  if (d.portLayoutOverrides !== undefined) for (const [key, value] of Object.entries(object(d.portLayoutOverrides, 'portLayoutOverrides'))) {
    let binding: unknown;
    try { binding = JSON.parse(key); } catch { throw new ValidationError('portLayoutOverrides: invalid binding key'); }
    if (!Array.isArray(binding) || binding.length !== 4 || !binding.every(item => typeof item === 'string')) throw new ValidationError('portLayoutOverrides: invalid binding key');
    const [ownerId, nodeId, portId, role] = binding;
    reference(ownerId, nodeIds, 'portLayoutOverrides.owner'); reference(nodeId, nodeIds, 'portLayoutOverrides.node');
    if (!a.nodes.find(node => node.id === nodeId)!.ports.some(port => port.id === portId)) throw new ValidationError('portLayoutOverrides: unknown port');
    member(role, ['data', 'residual', 'memory', 'mask'], 'portLayoutOverrides.role');
    if (value === null) continue;
    const layout = object(value, 'portLayout'); fields(layout, ['side', 'offset'], 'portLayout');
    member(layout.side, ['top', 'right', 'bottom', 'left'], 'portLayout.side');
    if (finite(layout.offset, 'portLayout.offset') < 0 || Number(layout.offset) > 1) throw new ValidationError('portLayout.offset: expected 0–1');
  }
  const legendIds: string[] = [];
  for (const lv of array(d.legendItems, 'legendItems')) { const l = object(lv, 'legend'); fields(l, ['id', 'label', 'color', 'glyph'], 'legend'); legendIds.push(textValue(l.id, 'legend.id')); textValue(l.label, 'legend.label'); color(l.color, 'legend.color'); member(l.glyph, GLYPHS, 'legend.glyph'); }
  unique(legendIds, 'legendItems');
  const annotationIds: string[] = [];
  for (const av of array(d.annotations, 'annotations')) {
    const a = object(av, 'annotation'); fields(a, ['id', 'text', 'x', 'y', 'width', 'height'], 'annotation');
    annotationIds.push(textValue(a.id, 'annotation.id')); textValue(a.text, 'annotation.text'); finite(a.x, 'annotation.x'); finite(a.y, 'annotation.y');
    for (const k of ['width', 'height']) if (a[k] !== undefined && finite(a[k], `annotation.${k}`) <= 0) throw new ValidationError(`annotation.${k}: positive value required`);
  }
  unique(annotationIds, 'annotations');
  const page = object(d.pageSpec, 'pageSpec'); fields(page, ['widthMm', 'background', 'preset'], 'pageSpec');
  if (finite(page.widthMm, 'pageSpec.widthMm') < 25 || Number(page.widthMm) > 1000) throw new ValidationError('pageSpec.widthMm: outside supported interval');
  color(page.background, 'pageSpec.background'); member(page.preset, ['paper', 'monochrome'], 'pageSpec.preset');
  for (const key of ['expandedIds', 'pinnedObjects']) { const ids = strings(d[key], key); unique(ids, key); for (const id of ids) reference(id, nodeIds, key); }
  for (const id of d.expandedIds as string[]) if (!a.nodes.find(n => n.id === id)!.children.length) throw new ValidationError(`expandedIds: ${id} has no recovered children`);
  function positions(value: unknown, path: string) {
    for (const [id, pv] of Object.entries(object(value, path))) {
      reference(id, nodeIds, path); const p = object(pv, 'position'); fields(p, ['x', 'y', 'width', 'height'], 'position');
      finite(p.x, 'position.x'); finite(p.y, 'position.y');
      for (const k of ['width', 'height']) if (p[k] !== undefined && finite(p[k], `position.${k}`) <= 0) throw new ValidationError(`position.${k}: positive value required`);
    }
  }
  positions(d.layout, 'layout');
  for (const [key, pv] of Object.entries(object(d.layoutByFrontier, 'layoutByFrontier'))) positions(pv, `layoutByFrontier.${key}`);
  return value as CanvasDocument;
}
