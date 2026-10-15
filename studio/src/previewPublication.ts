import type { ExportArtifact } from './api.ts';

export type PreviewExportBinding = { caseId: string; sourceDigest?: string; irDigest?: string; revision?: number };
export type PreviewExportSource = { svg: (nodeId?: string) => Promise<string>; binding: PreviewExportBinding; detailChoices?: { nodeId: string; pathLabel: string }[]; editingDocument?: string; sourcePackage?: string };
export type PreviewPublicationMetrics = { widthMm: number; heightMm: number; minTextPt: number; nodeLabelPt: number; minMainLinePt: number;
  suggestedWidthFor7Pt: number; suggestedHeightFor7Pt: number };
export type PreviewPublication = { svg: string; physical: PreviewPublicationMetrics; viewBox: [number, number, number, number] };
const NS = 'http://www.w3.org/2000/svg';
const common = ['id', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'opacity', 'fill-opacity', 'stroke-opacity', 'transform',
  'font-family', 'font-size', 'font-weight', 'letter-spacing', 'text-anchor', 'aria-label', 'role'];
const attributes: Record<string, string[]> = {
  svg: ['width', 'height', 'viewBox', 'preserveAspectRatio', 'data-document-id', 'data-revision'],
  g: ['data-node-id', 'data-canonical-id', 'data-edge-id', 'data-tensor-id', 'data-legend-id', 'data-annotation-id', 'data-edge-legend-id', 'data-edge-role', 'data-source-relation-id', 'data-source-relation-legend'],
  rect: ['x', 'y', 'width', 'height', 'rx', 'ry'], circle: ['cx', 'cy', 'r', 'data-port-id', 'data-node-id'],
  path: ['d', 'marker-end', 'marker-start', 'marker-mid', 'data-caption-guide-id', 'data-caption-for-edge', 'pointer-events'],
  text: ['x', 'y', 'dx', 'dy', 'textLength', 'lengthAdjust'], tspan: ['x', 'y', 'dx', 'dy'], title: [], metadata: [], defs: [],
  marker: ['viewBox', 'refX', 'refY', 'markerWidth', 'markerHeight', 'orient', 'markerUnits'],
  line: ['x1', 'y1', 'x2', 'y2'], polyline: ['points'], polygon: ['points'], ellipse: ['cx', 'cy', 'rx', 'ry'],
};
const styleAttributes = new Set(common.filter(name => !['id', 'aria-label', 'role', 'transform'].includes(name)));
const numericPaint = new Set(['stroke-width', 'opacity', 'fill-opacity', 'stroke-opacity', 'font-size', 'letter-spacing']);
function paint(value: string, name: string): string {
  if (numericPaint.has(name)) return value.trim().replace(/px$/, '');
  if (name === 'fill' || name === 'stroke') {
    const names: Record<string, string> = { black: '#000000', white: '#ffffff', red: '#ff0000', blue: '#0000ff', green: '#008000', gray: '#808080', grey: '#808080' };
    const rgb = /^rgb\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)\s*\)$/.exec(value.trim());
    if (rgb) return '#' + rgb.slice(1).map(channel => Math.min(255, Number(channel)).toString(16).padStart(2, '0')).join('');
    return names[value.toLowerCase()] ?? value;
  }
  return value;
}
function declarations(raw: string): [string, string][] {
  return raw.split(';').flatMap(item => {
    const colon = item.indexOf(':'), name = item.slice(0, colon).trim(), value = item.slice(colon + 1).trim().replace(/\s*!important\s*$/, '');
    return colon > 0 && styleAttributes.has(name) && !/url\s*\(|expression\s*\(/i.test(value) ? [[name, paint(value, name)] as [string, string]] : [];
  });
}
function hiddenStyle(raw: string): boolean {
  return /(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse))\s*(?:!important\s*)?(?:;|$)/i.test(raw);
}
function visible(element: Element): boolean {
  let current: Element | null = element;
  while (current) {
    if (current.getAttribute('display') === 'none' || ['hidden', 'collapse'].includes(current.getAttribute('visibility') ?? '') ||
      current.getAttribute('opacity') !== null && Number(current.getAttribute('opacity')) <= 0) return false;
    current = current.parentElement;
  }
  return true;
}
function inheritedNumber(element: Element, attribute: string, fallback: number): number {
  let current: Element | null = element;
  while (current) { const value = current.getAttribute(attribute); if (value !== null && value !== '') { const parsed = Number(value); if (Number.isFinite(parsed)) return parsed; } current = current.parentElement; }
  return fallback;
}

/** Preserve the rendered geometry and inline supported paint before embedding or publication conversion. */
export function sanitizePreviewPublication(raw: string, widthMm: number): PreviewPublication {
  if (typeof raw !== 'string' || !raw || new TextEncoder().encode(raw).length > 8_000_000 || /<!\s*(?:DOCTYPE|ENTITY)|<\?/i.test(raw)) throw new Error('预览 SVG 内容无效或超过 8 MB。');
  if (!Number.isFinite(widthMm) || widthMm < 25 || widthMm > 1000) throw new Error('请输入 25–1000 mm 之间的页宽。');
  const parsed = new DOMParser().parseFromString(raw, 'image/svg+xml'), root = parsed.documentElement;
  if (parsed.querySelector('parsererror') || root.localName !== 'svg' || root.namespaceURI !== NS) throw new Error('预览 SVG 不是有效的独立 SVG。');
  const viewBox = (root.getAttribute('viewBox') ?? '').trim().split(/[\s,]+/).map(Number);
  if (viewBox.length !== 4 || viewBox.some(value => !Number.isFinite(value)) || viewBox[2] <= 0 || viewBox[3] <= 0) throw new Error('预览 SVG 缺少有效的 viewBox。');
  root.querySelectorAll('[data-editor-only],.wire-hit,.node-hit,.frame-hit,.expansion-control,#previewLayer,#handleLayer,#obstacleLayer,#ghostLayer').forEach(element => element.remove());
  // The iframe normally supplies computed paint. Preserve supported simple
  // stylesheet rules too, so class-based wire fill and fonts remain faithful.
  for (const style of root.querySelectorAll('style')) {
    const rules = (style.textContent ?? '').replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g);
    for (const [, selector, body] of rules) {
      if (selector.includes('@')) continue;
      try { for (const element of root.querySelectorAll(selector.trim())) {
        if (hiddenStyle(body)) { element.remove(); continue; }
        for (const [name, value] of declarations(body)) element.setAttribute(name, value);
      } } catch { /* Unsupported selectors contribute no paint. */ }
    }
    style.remove();
  }
  const all = [root, ...root.querySelectorAll('*')];
  if (all.length > 30_000) throw new Error('预览 SVG 超过 30000 元素。');
  for (const element of all) {
    if (!element.isConnected) continue;
    if (element.namespaceURI !== NS || !attributes[element.localName] || (element.localName === 'svg' && element !== root)) { element.remove(); continue; }
    if (element !== root && (hiddenStyle(element.getAttribute('style') ?? '') || !visible(element))) { element.remove(); continue; }
    for (const [name, value] of declarations(element.getAttribute('style') ?? '')) element.setAttribute(name, value);
    for (const name of ['fill', 'stroke', ...numericPaint]) { const value = element.getAttribute(name); if (value !== null) element.setAttribute(name, paint(value, name)); }
    const allowed = new Set([...common, ...attributes[element.localName]]);
    for (const attribute of [...element.attributes]) {
      if (attribute.name === 'xmlns' && element === root) continue;
      if (!allowed.has(attribute.name) || /url\s*\(/i.test(attribute.value) && !/^marker-(?:start|mid|end)$/.test(attribute.name)) element.removeAttribute(attribute.name);
    }
    // Hit targets have already been removed; pointer-events is reserved by
    // the server for identified caption-guide paths.
    if (element.hasAttribute('pointer-events') && !element.hasAttribute('data-caption-guide-id')) element.removeAttribute('pointer-events');
  }
  const unitPt = widthMm * 72 / 25.4 / viewBox[2];
  const fonts = [...root.querySelectorAll('text,tspan')].filter(element => element.textContent?.trim() && !element.closest('defs') && visible(element))
    .map(element => ({ size: inheritedNumber(element, 'font-size', 16), title: element.getAttribute('font-weight') === 'bold' || inheritedNumber(element, 'font-weight', 400) >= 600 })).filter(font => font.size > 0);
  const minFont = Math.min(...fonts.map(font => font.size), fonts.length ? Infinity : 16);
  const titleFonts = fonts.filter(font => font.title), labelFont = Math.min(...(titleFonts.length ? titleFonts : fonts).map(font => font.size), fonts.length ? Infinity : 16);
  const lines = [...root.querySelectorAll('path,line,polyline')].filter(element => !element.closest('defs') && element.getAttribute('stroke') !== 'none')
    .map(element => inheritedNumber(element, 'stroke-width', 1)).filter(width => width > 0);
  const suggestedWidthFor7Pt = Math.ceil(7 / minFont * viewBox[2] * 25.4 / 72), heightMm = widthMm * viewBox[3] / viewBox[2];
  root.setAttribute('width', `${widthMm}mm`); root.setAttribute('height', `${heightMm}mm`);
  return { svg: new XMLSerializer().serializeToString(root), viewBox: viewBox as [number, number, number, number], physical: { widthMm, heightMm,
    minTextPt: minFont * unitPt, nodeLabelPt: labelFont * unitPt, minMainLinePt: Math.min(...lines, lines.length ? Infinity : 1) * unitPt,
    suggestedWidthFor7Pt, suggestedHeightFor7Pt: suggestedWidthFor7Pt * viewBox[3] / viewBox[2] } };
}

/** Changing range or physical size invalidates every earlier SVG and conversion response. */
export class PreviewPublicationRequestGate {
  private sequence = 0;
  begin(): number { return ++this.sequence; }
  invalidate(): void { this.sequence++; }
  isCurrent(sequence: number): boolean { return sequence === this.sequence; }
}
export function previewPublicationCacheKey(svg: string, binding: PreviewExportBinding, options: { scope: string; nodeId?: string; widthMm: number; format: string; dpi: number }): string {
  return JSON.stringify([svg, binding.caseId, binding.sourceDigest ?? null, binding.irDigest ?? null, binding.revision ?? null,
    options.scope, options.nodeId ?? null, options.widthMm, options.format, options.dpi]);
}
export function readPreviewPublicationCache(raw: string | null, key: string): ExportArtifact | null {
  try { const cached = JSON.parse(raw ?? 'null'), artifact = cached?.artifact;
    return cached?.schemaVersion === 1 && cached.key === key && artifact && ['svg', 'pdf', 'png'].includes(artifact.format) && typeof artifact.url === 'string' && typeof artifact.receiptUrl === 'string' ? artifact : null;
  } catch { return null; }
}
export function writePreviewPublicationCache(artifact: ExportArtifact, key: string): string { return JSON.stringify({ schemaVersion: 1, key, artifact }); }
