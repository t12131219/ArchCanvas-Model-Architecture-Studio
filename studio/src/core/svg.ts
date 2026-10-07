import type { Glyph, Scene, SceneNode } from './types.ts';
import { edgeDashPattern } from './edgePresentation.ts';
import { TOKENS } from './tokens.ts';
import { textWidth, wrapText } from './typography.ts';
import { outputPathText } from './nodeFacts.ts';
import { nodeVisualOutline } from './nodeVisualOutline.ts';

export function escapeXml(value: unknown): string { return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]!)); }
const n = (value: number) => String(Math.round(value * 100) / 100);
const attr = (value: unknown) => escapeXml(value);
function dashAttribute(appearance: { dashed: boolean; dashPattern?: number[] }): string {
  const pattern = edgeDashPattern(appearance);
  return pattern.length ? ` stroke-dasharray="${attr(pattern.join(' '))}"` : '';
}
function lines(text: string, max: number): string[] {
  const result: string[] = [];
  for (const paragraph of text.split('\n')) {
    let line = '';
    for (const word of paragraph.split(/(\s+)/)) {
      if (line.length + word.length > max && line) { result.push(line.trim()); line = ''; }
      if (word.length > max) { for (const c of [...word]) { if ([...line].length >= max) { result.push(line); line = ''; } line += c; } } else line += word;
    }
    result.push(line.trim());
  }
  return result;
}
function glyph(type: Glyph, x: number, y: number, color: string): string {
  const start = `<g transform="translate(${n(x)} ${n(y)})" fill="none" stroke="${attr(color)}" stroke-width="1.4" stroke-linecap="round">`;
  const shapes: Record<Glyph, string> = {
    module: '<rect x="-7" y="-7" width="14" height="14" rx="3"/><path d="M-3-7V7M3-7V7" opacity=".45"/>',
    operator: '<rect x="-7" y="-7" width="14" height="14" rx="3"/><path d="M-3 0H3M0-3V3"/>',
    tensor: '<rect x="-8" y="-6" width="16" height="12" rx="1"/><path d="M-3-6V6M3-6V6M-8 0H8" opacity=".6"/>',
    add: '<circle r="8"/><path d="M-4 0H4M0-4V4"/>',
    attention: '<path d="M-8-5H8M-8 0H8M-8 5H8M-5-7L5 7M5-7L-5 7"/>',
    norm: '<path d="M-7-6H7M-7 0H7M-7 6H7M-2-8V8"/>',
    opaque: '<rect x="-7" y="-7" width="14" height="14" rx="3" stroke-dasharray="3 2"/><path d="M-2-3Q3-5 3-1L0 2M0 5V5.2"/>',
  };
  return start + shapes[type] + '</g>';
}

function renderNode(node: SceneNode, interactive: boolean): string {
  const id = attr(node.id), x = n(node.x), y = n(node.y), w = n(node.width), h = n(node.height);
  const dashed = node.evidence === 'opaque' ? ' stroke-dasharray="5 3"' : '';
  const fact = node.sourceFact;
  const identity = [fact?.instanceId ? `instance ${fact.instanceId}` : '', fact?.callId ? `call ${fact.callId}` : '',
    fact?.outputPath ? outputPathText(fact.outputPath) : '', fact?.source ? `${fact.source.path}:${fact.source.line}` : ''].filter(Boolean).join(' · ');
  let output = `<g data-node-id="${id}" data-canonical-id="${attr(node.canonicalNodeId ?? node.id)}" aria-label="${attr(node.label)}"${interactive ? ' tabindex="0" role="button"' : ''}><title>${attr(node.label)} · ${attr(node.kind)} · ${attr(node.evidence)}${identity ? ` · ${attr(identity)}` : ''}</title>`;
  output += nodeVisualOutline(node).backplates.map((plate, index) => `<rect x="${n(plate.x)}" y="${n(plate.y)}" width="${n(plate.width)}" height="${n(plate.height)}" rx="9" fill="${attr(node.fill)}" stroke="${attr(node.stroke)}" opacity="${index ? '.7' : '.45'}"/>`).join('');
  output += `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${node.expanded ? 12 : 9}" fill="${attr(node.fill)}" stroke="${attr(node.stroke)}" stroke-width="${node.expanded ? 1.3 : 1.5}"${dashed}/>`;
  if (node.expanded) {
    output += `<path d="M ${n(node.x + 1)} ${n(node.y + node.headerHeight - 4)} H ${n(node.x + node.width - 1)}" stroke="${attr(node.stroke)}" opacity=".28"/>`;
    output += glyph(node.glyph, node.x + 23, node.y + 23, node.stroke);
    output += `<text x="${n(node.x + 43)}" y="${n(node.y + 27)}" fill="${TOKENS.ink}" font-size="13" font-weight="600">${wrapText(node.label, node.width - 90).map((line, i) => `<tspan x="${n(node.x + 43)}" dy="${i ? '16' : '0'}">${attr(line)}</tspan>`).join('')}</text>`;
    if (node.repeat) output += `<text x="${n(node.x + node.width - (interactive ? 47 : 17))}" y="${n(node.y + 27)}" fill="${TOKENS.muted}" font-size="10" text-anchor="end">${node.repeat.count}× · ${attr(node.repeat.sharing)}</text>`;
  } else {
    output += glyph(node.glyph, node.x + 25, node.y + node.height / 2, node.stroke);
    const labelLines = wrapText(node.label, node.width - 62);
    const cy = node.y + (labelLines.length > 1 ? 23 : 26);
    output += `<text x="${n(node.x + 45)}" y="${n(cy)}" fill="${TOKENS.ink}" font-size="13" font-weight="600">${labelLines.map((line, i) => `<tspan x="${n(node.x + 45)}" dy="${i ? '16' : '0'}">${attr(line)}</tspan>`).join('')}</text>`;
    if (labelLines.length < 2 && node.height > 46) {
      const budget = node.width - 62;
      let subtitle = node.subtitle;
      if (textWidth(subtitle, 10) > budget) {
        while (subtitle && textWidth(`${subtitle}…`, 10) > budget) subtitle = [...subtitle].slice(0, -1).join('');
        subtitle += '…';
      }
      output += `<text x="${n(node.x + 45)}" y="${n(node.y + 43)}" fill="${TOKENS.muted}" font-size="10">${attr(subtitle)}</text>`;
    }
  }
  if (interactive && node.expandable) output += `<g data-expand-id="${id}" role="button" aria-label="${node.expanded ? 'Collapse' : 'Expand'} ${attr(node.label)}"><rect x="${n(node.x + node.width - 29)}" y="${n(node.y + 11)}" width="18" height="18" rx="5" fill="#ffffff" stroke="${attr(node.stroke)}"/><path d="M ${n(node.x + node.width - 24)} ${n(node.y + 20)} h 8${node.expanded ? '' : ` M ${n(node.x + node.width - 20)} ${n(node.y + 16)} v 8`}" stroke="${attr(node.stroke)}" stroke-width="1.3"/></g>`;
  return output + '</g>';
}

/** The default output contains publication objects only; the UI opts into controls. */
export function svgBody(scene: Scene, options: { interactive?: boolean; background?: boolean } = {}): string {
  const interactive = options.interactive ?? false;
  const colors = [...new Set(scene.edges.map(e => e.stroke))];
  let svg = `<defs>${colors.map((color, i) => `<marker id="archcanvas-arrow-${i}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9 Z" fill="${attr(color)}"/></marker>`).join('')}</defs>`;
  if (options.background !== false) svg += `<rect x="${n(scene.bounds.x)}" y="${n(scene.bounds.y)}" width="${n(scene.bounds.width)}" height="${n(scene.bounds.height)}" fill="${attr(scene.pageSpec.background)}"/>`;
  svg += `<g font-family="${attr(TOKENS.font)}"><text x="50" y="40" fill="${TOKENS.ink}" font-size="19" font-weight="600">${attr(scene.title)}</text><text x="50" y="62" fill="${TOKENS.muted}" font-size="10" letter-spacing="1.4">MODEL ARCHITECTURE · SOURCE-BOUND VIEW</text>`;
  svg += scene.nodes.filter(node => node.expanded).map(node => renderNode(node, interactive)).join('');
  svg += `<g fill="none" stroke-linejoin="round" stroke-linecap="round">${scene.edges.map(e => `<g data-edge-id="${attr(e.id)}" data-tensor-id="${attr(e.tensorId)}"><title>${attr(e.id)} · ${attr(e.role)} · ${attr(e.tensorId)}</title><path d="${attr(e.path)}" stroke="${attr(e.stroke)}" stroke-width="${n(e.width)}"${dashAttribute(e)} marker-end="url(#archcanvas-arrow-${colors.indexOf(e.stroke)})"/>${e.label ? `<text x="${n(e.labelX)}" y="${n(e.labelY)}" font-size="9" fill="${attr(e.stroke)}" stroke="none">${attr(e.label)}</text>` : ''}</g>`).join('')}</g>`;
  svg += (scene.captionGuides ?? []).map(guide => `<path data-caption-guide-id="${attr(guide.id)}" data-caption-for-edge="${attr(guide.sceneEdgeId)}" d="${attr(guide.path)}" fill="none" stroke="${attr(guide.stroke)}" stroke-width="${n(guide.width)}" stroke-linecap="round" opacity=".65" pointer-events="none"><title>Caption guide · ${attr(guide.sceneEdgeId)}</title></path>`).join('');
  svg += scene.nodes.filter(node => !node.expanded).map(node => renderNode(node, interactive)).join('');
  svg += scene.nodes.flatMap(node => node.ports.map(p => interactive
    ? `<g data-port-id="${attr(p.id)}" data-node-id="${attr(node.id)}"><title>${attr(p.name)}${p.proxy ? ' · projected boundary port' : p.direction === 'in' ? ' · 拖向来源输出端口以创建改接提案' : ''}</title><circle cx="${n(p.x)}" cy="${n(p.y)}" r="8" fill="transparent"/><circle cx="${n(p.x)}" cy="${n(p.y)}" r="2.6" fill="${attr(node.stroke)}"/></g>`
    : `<circle data-port-id="${attr(p.id)}" data-node-id="${attr(node.id)}" cx="${n(p.x)}" cy="${n(p.y)}" r="2.6" fill="${attr(node.stroke)}"><title>${attr(p.name)}${p.proxy ? ' · projected boundary port' : ''}</title></circle>`)).join('');
  svg += scene.legend.map(l => `<g data-legend-id="${attr(l.id)}"><rect x="${n(l.x)}" y="${n(l.y - 11)}" width="19" height="15" rx="4" fill="${attr(l.color)}" stroke="#a0adbb"/>${glyph(l.glyph, l.x + 9.5, l.y - 3.5, '#718495')}<text x="${n(l.x + 29)}" y="${n(l.y)}" fill="${TOKENS.muted}" font-size="10">${attr(l.label)}</text></g>`).join('');
  svg += (scene.edgeLegend ?? []).map(item => {
    const sampleX = item.x + item.lineWidth * .55, sampleY = item.y + item.height / 2;
    const labelX = sampleX + item.sampleLength + Math.max(16, item.lineWidth * .55 + 8);
    return `<g data-edge-legend-id="${attr(item.id)}" data-edge-role="${attr(item.role)}"><path d="M ${n(sampleX)} ${n(sampleY)} H ${n(sampleX + item.sampleLength)}" fill="none" stroke="${attr(item.stroke)}" stroke-width="${n(item.lineWidth)}" stroke-linecap="round"${dashAttribute(item)} marker-end="url(#archcanvas-arrow-${colors.indexOf(item.stroke)})"/><text x="${n(labelX)}" y="${n(sampleY + 3.5)}" fill="${TOKENS.muted}" font-size="10">${attr(item.label)}</text></g>`;
  }).join('');
  svg += scene.annotations.map(a => `<g data-annotation-id="${attr(a.id)}"><rect x="${n(a.x)}" y="${n(a.y)}" width="${n(a.width)}" height="${n(a.height)}" rx="4" fill="#fffdf7" stroke="#d6c9a9" stroke-dasharray="3 3"/><text x="${n(a.x + 10)}" y="${n(a.y + 20)}" fill="#827453" font-size="11">${wrapText(a.text, a.width - 20, 11).map((line, i) => `<tspan x="${n(a.x + 10)}" dy="${i ? '15' : '0'}">${attr(line)}</tspan>`).join('')}</text></g>`).join('');
  return svg + '</g>';
}

export function renderSvg(scene: Scene, options: { interactive?: boolean; background?: boolean } = {}): string {
  const b = scene.bounds;
  const heightMm = scene.pageSpec.widthMm * b.height / b.width;
  const metadata = { renderer: 'archcanvas-svg/1.0', documentId: scene.documentId, revision: scene.revision,
    sourceDigest: scene.sourceDigest, irDigest: scene.irDigest, widthMm: scene.pageSpec.widthMm, heightMm,
    sourceFactScope: 'whole-source-architecture', sourceFacts: scene.sourceFacts,
    renderedNodes: scene.nodes.map(node => ({ sceneNodeId: node.id, canonicalNodeId: node.canonicalNodeId ?? node.id, boundary: node.boundary ?? false })),
    renderedBindings: scene.edges.map(edge => ({ sceneEdgeId: edge.id, canonicalEdgeIds: edge.canonicalEdgeIds,
      source: edge.source, target: edge.target, tensorId: edge.tensorId, role: edge.role })),
    ...(scene.captionGuides?.length ? { presentationDecorations: scene.captionGuides.map(guide => ({ id: guide.id, kind: guide.kind, sceneEdgeId: guide.sceneEdgeId, path: guide.path })) } : {}),
    ...(scene.exportScope ? { exportScope: scene.exportScope } : {}) };
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${n(scene.pageSpec.widthMm)}mm" height="${n(heightMm)}mm" viewBox="${n(b.x)} ${n(b.y)} ${n(b.width)} ${n(b.height)}" data-document-id="${attr(scene.documentId)}" data-revision="${scene.revision}" role="img" aria-label="${attr(scene.title)}"><metadata>${attr(JSON.stringify(metadata))}</metadata>${svgBody(scene, options)}</svg>`;
}
