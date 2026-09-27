import type {
  KernelDocument,
  KernelRenderScene,
  KernelVisualState,
  RenderDetailPrimitive,
  RenderNode,
} from "./types";
import { NODE_TOKENS, RELATION_TOKENS } from "./visual-language";

export const KERNEL_EXPORT_VERSION = "visual-kernel-svg-v1";

export interface KernelExportArtifact {
  svg: string;
  renderDigest: string;
  width: number;
  height: number;
  sceneId: string;
  sourceDigest: string;
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, stableValue(item)]));
  }
  return value;
}

function hashString(value: string): string {
  let first = 0x811c9dc5;
  let second = 0x9e3779b9;
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    first = Math.imul(first ^ code, 0x01000193) >>> 0;
    second = Math.imul(second ^ code, 0x85ebca6b) >>> 0;
  }
  return `${first.toString(16).padStart(8, "0")}${second.toString(16).padStart(8, "0")}`;
}

export function kernelSceneDigest(
  document: KernelDocument,
  visualState: KernelVisualState,
  scene: KernelRenderScene,
): string {
  const payload = {
    version: KERNEL_EXPORT_VERSION,
    document: {
      documentId: document.documentId,
      architectureId: document.architectureId,
      sourceDigest: document.sourceDigest,
    },
    styles: {
      routeStyle: visualState.routeStyle,
      nodeStyle: visualState.nodeStyle,
      labelStyle: visualState.labelStyle,
    },
    scene: {
      sceneId: scene.sceneId,
      sourceDigest: scene.sourceDigest,
      width: scene.width,
      height: scene.height,
      nodes: [...scene.nodes].sort((a, b) => a.nodeId.localeCompare(b.nodeId)),
      edges: [...scene.edges].sort((a, b) => a.edgeId.localeCompare(b.edgeId)),
      portals: [...scene.portals].sort((a, b) => a.portalId.localeCompare(b.portalId)),
      details: [...scene.details].sort((a, b) => a.bindingId.localeCompare(b.bindingId)),
    },
  };
  return `kernel-render:${hashString(JSON.stringify(stableValue(payload)))}`;
}

function escapeXml(value: unknown): string {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function data(name: string, value: string | string[] | undefined): string {
  if (value === undefined || value.length === 0) return "";
  return ` data-${name}=\"${escapeXml(Array.isArray(value) ? value.join(" ") : value)}\"`;
}

function glyph(node: RenderNode): string {
  const x = node.bounds.x + 12;
  const shape = node.shape;
  if (shape === "tensor") {
    const y = node.bounds.y + 22;
    return `<g class="kernel-node-glyph matrix-glyph"><path d="M${x + 6} ${y - 6}h52l7 7v44l-7-7h-52z"/><rect x="${x}" y="${y}" width="52" height="44" rx="2"/>${[1, 2, 3].map((column) => `<line x1="${x + column * 13}" y1="${y}" x2="${x + column * 13}" y2="${y + 44}"/>`).join("")}${[1, 2].map((row) => `<line x1="${x}" y1="${y + row * 14.6666666667}" x2="${x + 52}" y2="${y + row * 14.6666666667}"/>`).join("")}</g>`;
  }
  if (shape === "operation") {
    const y = node.bounds.y + 24;
    return `<g class="kernel-node-glyph operation-glyph">${[[0, 17], [12, 22], [24, 27]].map(([offset, width]) => `<rect x="${x}" y="${y + offset}" width="${width}" height="6" rx="1.5"/>`).join("")}</g>`;
  }
  if (shape === "convolution") {
    const y = node.bounds.y + 23;
    return `<g class="kernel-node-glyph convolution-glyph">${[8, 4, 0].map((offset) => `<rect x="${x + offset}" y="${y - offset}" width="45" height="42" rx="2"/>`).join("")}${[1, 2].map((column) => `<line x1="${x + 8 + column * 15}" y1="${y - 8}" x2="${x + 8 + column * 15}" y2="${y + 34}"/>`).join("")}${[1, 2].map((row) => `<line x1="${x + 8}" y1="${y - 8 + row * 14}" x2="${x + 53}" y2="${y - 8 + row * 14}"/>`).join("")}</g>`;
  }
  if (shape === "attention") {
    const y = node.bounds.y + 20;
    return `<g class="kernel-node-glyph attention-glyph">${["Q", "K", "V"].map((value, index) => `<g><rect x="${x}" y="${y + index * 15.5}" width="17" height="12.6666666667" rx="2"/><text class="kernel-node-glyph-text" x="${x + 8.5}" y="${y + index * 15.5 + 10.3333333333}">${value}</text><line x1="${x + 18}" y1="${y + index * 15.5 + 6.3333333333}" x2="${x + 44}" y2="${y + 22}"/></g>`).join("")}<circle cx="${x + 48}" cy="${y + 22}" r="5"/></g>`;
  }
  if (shape === "normalization") {
    const y = node.bounds.y + 24;
    return `<g class="kernel-node-glyph normalization-glyph"><rect x="${x}" y="${y}" width="54" height="38" rx="19"/>${[20, 27, 34].map((offset) => `<line x1="${x + offset}" y1="${y + 8}" x2="${x + offset}" y2="${y + 30}"/>`).join("")}<text class="kernel-node-glyph-text" x="${x + 27}" y="${y + 22}">mu s</text></g>`;
  }
  if (shape === "container") {
    const y = node.bounds.y + 20;
    return `<g class="kernel-node-glyph container-glyph"><rect x="${x}" y="${y}" width="48" height="48" rx="3"/><rect x="${x + 7}" y="${y + 9}" width="13" height="12" rx="2"/><rect x="${x + 28}" y="${y + 9}" width="13" height="12" rx="2"/><rect x="${x + 17}" y="${y + 29}" width="14" height="11" rx="2"/><path d="M${x + 20} ${y + 15}h8M${x + 34} ${y + 21}v8M${x + 17} ${y + 34}h-5v-13"/></g>`;
  }
  return "";
}

function nodeShape(node: RenderNode): string {
  const { x, y, width, height } = node.bounds;
  const token = NODE_TOKENS[node.shape];
  const style = `fill="${token.fill}" stroke="${token.stroke}" class="kernel-node-body"`;
  if (node.shape === "condition") {
    const inset = Math.min(24, width * 0.15);
    return `<polygon ${style} points="${x + inset},${y} ${x + width - inset},${y} ${x + width},${y + height / 2} ${x + width - inset},${y + height} ${x + inset},${y + height} ${x},${y + height / 2}"/>`;
  }
  if (node.shape === "merge") {
    const cx = x + width / 2;
    const cy = y + 31;
    return `<polygon ${style} points="${cx},${cy - 24} ${cx + 24},${cy} ${cx},${cy + 24} ${cx - 24},${cy}"/>`;
  }
  if (["add", "multiply", "concat"].includes(node.shape)) return `<circle ${style} cx="${x + width / 2}" cy="${y + 31}" r="24"/>`;
  const rx = node.shape === "io" ? Math.min(28, height / 2) : node.shape === "normalization" ? 14 : node.shape === "container" ? 6 : 5;
  return `<rect ${style} x="${x}" y="${y}" width="${width}" height="${height}" rx="${rx}"/>`;
}

function renderExpandedNode(node: RenderNode, fidelity: string | undefined): string {
  const { x, y, width, height } = node.bounds;
  return `<g class="kernel-expanded-module module-detail scene-node shape-${node.shape} role-${node.renderRole}"${data("kernel-node-id", node.nodeId)}${data("hierarchy-node-id", node.hierarchyNodeId)}${data("canonical-node-ids", node.canonicalNodeIds)}${data("input-port-ids", node.inputPortIds)}${data("output-port-ids", node.outputPortIds)}${data("evidence-ids", node.evidenceIds)}${data("template-binding-id", node.templateBindingId)}${data("template-fidelity", fidelity)}><rect class="kernel-expanded-surface nested-inline-surface node-surface" x="${x}" y="${y}" width="${width}" height="${height}" rx="6"/><path class="kernel-expanded-header nested-inline-header" d="M${x + 6} ${y}h${width - 12}a6 6 0 0 1 6 6v44h-${width}v-44a6 6 0 0 1 6-6z"/><line class="kernel-expanded-divider nested-inline-divider" x1="${x}" y1="${y + 50}" x2="${x + width}" y2="${y + 50}"/><text class="kernel-expanded-title nested-detail-title" x="${x + 16}" y="${y + 22}">${escapeXml(node.label)}</text><text class="kernel-expanded-subtitle nested-detail-subtitle" x="${x + 16}" y="${y + 39}">${node.childNodeIds.length} visible modules &#183; ${node.containedCanonicalNodeIds.length} canonical</text></g>`;
}

function renderStandardNode(node: RenderNode, nodeStyle: KernelVisualState["nodeStyle"], incoming: number, outgoing: number, fidelity: string | undefined): string {
  const symbolNode = ["add", "multiply", "concat"].includes(node.shape);
  const hasGlyph = ["tensor", "container", "operation", "convolution", "attention", "normalization"].includes(node.shape);
  const textX = hasGlyph ? node.bounds.x + node.bounds.width * 0.69 : node.bounds.x + node.bounds.width / 2;
  const titleX = symbolNode ? node.bounds.x + node.bounds.width / 2 : textX;
  const titleY = symbolNode ? node.bounds.y + 72 : node.bounds.y + node.bounds.height / 2 - (node.secondaryLabel ? 6 : 0);
  const symbol = node.shape === "concat" ? "||" : node.shape === "multiply" ? "×" : "+";
  return `<g class="kernel-node scene-node shape-${node.shape} role-${node.renderRole}"${data("kernel-node-id", node.nodeId)}${data("hierarchy-node-id", node.hierarchyNodeId)}${data("canonical-node-ids", node.canonicalNodeIds)}${data("input-port-ids", node.inputPortIds)}${data("output-port-ids", node.outputPortIds)}${data("evidence-ids", node.evidenceIds)}${data("template-binding-id", node.templateBindingId)}${data("template-fidelity", fidelity)}>${nodeShape(node).replace("kernel-node-body", "kernel-node-body node-surface")}${glyph(node)}${symbolNode ? `<text class="kernel-node-symbol node-symbol" text-anchor="middle" x="${node.bounds.x + node.bounds.width / 2}" y="${node.bounds.y + 39}">${symbol}</text>` : ""}<text class="kernel-node-title node-label${symbolNode ? " symbol-label" : ""}" text-anchor="middle" x="${titleX}" y="${titleY}">${escapeXml(node.label)}</text>${!symbolNode && node.secondaryLabel ? `<text class="kernel-node-secondary node-detail" text-anchor="middle" x="${textX}" y="${node.bounds.y + node.bounds.height / 2 + 14}">${escapeXml(node.secondaryLabel)}</text>` : ""}${nodeStyle === "technical" ? `<text class="kernel-node-ports node-kind" text-anchor="middle" x="${textX}" y="${node.bounds.y + node.bounds.height - 9}">${incoming} in &#183; ${outgoing} out</text>` : ""}</g>`;
}

function toneClass(primitive: RenderDetailPrimitive): string {
  return `tone-${primitive.tone}`;
}

function renderDetailPrimitive(primitive: RenderDetailPrimitive, evidenceIds: string[]): string {
  const attrs = `${data("detail-primitive-id", primitive.primitiveId)}${data("detail-slot-id", primitive.slotId)}${data("canonical-node-ids", primitive.canonicalIds)}${data("evidence-ids", evidenceIds)}`;
  if (primitive.kind === "flow") {
    const points = primitive.points.map((point) => `${point.x},${point.y}`).join(" ");
    return `<polyline class="kernel-detail-flow detail-flow ${toneClass(primitive)} detail-${toneClass(primitive)}"${attrs} points="${points}"${primitive.marker ? ' marker-end="url(#kernel-detail-arrow)"' : ""}/>`;
  }
  if (primitive.kind === "box") {
    const frame = primitive.slotId.startsWith("frame:");
    const capsule = primitive.slotId.startsWith("capsule:");
    return `<g class="kernel-detail-box detail-shape detail-box ${toneClass(primitive)} detail-${toneClass(primitive)}${frame ? " kernel-detail-frame detail-frame" : ""}${capsule ? " kernel-detail-capsule detail-capsule" : ""}"${attrs}><rect x="${primitive.x}" y="${primitive.y}" width="${primitive.width}" height="${primitive.height}" rx="${frame ? 5 : capsule ? primitive.height / 2 : 3}"/>${primitive.label ? `<text class="kernel-detail-label detail-box-label" text-anchor="middle" x="${primitive.x + primitive.width / 2}" y="${primitive.y + primitive.height / 2 + (primitive.note ? -3 : 4)}">${escapeXml(primitive.label)}</text>` : ""}${primitive.note ? `<text class="kernel-detail-note detail-note" text-anchor="middle" x="${primitive.x + primitive.width / 2}" y="${primitive.y + primitive.height / 2 + 12}">${escapeXml(primitive.note)}</text>` : ""}</g>`;
  }
  if (primitive.kind === "matrix") {
    const columnWidth = primitive.width / primitive.columns;
    const rowHeight = primitive.height / primitive.rows;
    const depth = primitive.depth > 0 ? `<path class="kernel-detail-matrix-depth" d="M${primitive.x + primitive.depth} ${primitive.y - primitive.depth}h${primitive.width}v${primitive.height}M${primitive.x + primitive.width} ${primitive.y}l${primitive.depth} -${primitive.depth}M${primitive.x + primitive.width} ${primitive.y + primitive.height}l${primitive.depth} -${primitive.depth}"/>` : "";
    const columns = Array.from({ length: primitive.columns - 1 }, (_, index) => `<line x1="${primitive.x + columnWidth * (index + 1)}" y1="${primitive.y}" x2="${primitive.x + columnWidth * (index + 1)}" y2="${primitive.y + primitive.height}"/>`).join("");
    const rows = Array.from({ length: primitive.rows - 1 }, (_, index) => `<line x1="${primitive.x}" y1="${primitive.y + rowHeight * (index + 1)}" x2="${primitive.x + primitive.width}" y2="${primitive.y + rowHeight * (index + 1)}"/>`).join("");
    return `<g class="kernel-detail-matrix detail-shape detail-matrix ${toneClass(primitive)} detail-${toneClass(primitive)}"${attrs}>${depth}<rect x="${primitive.x}" y="${primitive.y}" width="${primitive.width}" height="${primitive.height}" rx="2"/><g class="node-grid">${columns}${rows}</g><text class="detail-matrix-label" text-anchor="middle" x="${primitive.x + primitive.width / 2}" y="${primitive.y - 7}">${escapeXml(primitive.label)}</text></g>`;
  }
  if (primitive.kind === "operator") return `<g class="kernel-detail-operator detail-shape ${toneClass(primitive)} detail-${toneClass(primitive)}"${attrs}><circle cx="${primitive.cx}" cy="${primitive.cy}" r="${primitive.radius}"/><text class="detail-symbol" text-anchor="middle" x="${primitive.cx}" y="${primitive.cy + 4}">${escapeXml(primitive.label)}</text></g>`;
  return `<text class="kernel-detail-text detail-text ${toneClass(primitive)}${primitive.emphasis ? " emphasis" : ""}"${attrs} text-anchor="middle" x="${primitive.x}" y="${primitive.y}">${escapeXml(primitive.value)}</text>`;
}

const SVG_STYLE = `
svg{background:#fbfcfa;color:#263037;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.kernel-paper{fill:#f7f8f6}.kernel-grid{opacity:.62;stroke:#dfe3e1;stroke-width:.7}.kernel-edge path{fill:none;stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round}.kernel-edge-label rect{fill:#fff;stroke:#cfd5d1;stroke-width:.7}.kernel-edge-label text,.kernel-endpoint-labels text{fill:#303632;font-size:10px;letter-spacing:0}.kernel-portal,.kernel-detail-boundary-portal{fill:#fbfcfa;stroke:#397b73;stroke-width:1.4}.kernel-portal.exit,.kernel-detail-boundary-portal.exit{fill:#397b73}.kernel-detail-flow{fill:none;stroke:#68706a;stroke-width:1.25;stroke-linecap:round;stroke-linejoin:round}.kernel-detail-flow.tone-blue{stroke:#3b789e}.kernel-detail-flow.tone-green{stroke:#397b63}.kernel-detail-flow.tone-pink{stroke:#a45d7d}.kernel-detail-flow.tone-orange{stroke:#a5652e}.kernel-detail-flow.tone-violet{stroke:#7156a0}.kernel-detail-box rect,.kernel-detail-matrix rect,.kernel-detail-matrix line,.kernel-detail-matrix-depth,.kernel-detail-operator circle{stroke:#69736d;stroke-width:1.1}.kernel-detail-box rect,.kernel-detail-matrix rect,.kernel-detail-operator circle{fill:#f4f6f4}.kernel-detail-box.tone-blue rect,.kernel-detail-matrix.tone-blue rect{fill:#e5f3fb;stroke:#3b789e}.kernel-detail-box.tone-green rect,.kernel-detail-matrix.tone-green rect{fill:#e6f5ec;stroke:#397b63}.kernel-detail-box.tone-pink rect,.kernel-detail-matrix.tone-pink rect{fill:#f9e7ef;stroke:#a45d7d}.kernel-detail-box.tone-orange rect,.kernel-detail-matrix.tone-orange rect,.kernel-detail-operator.tone-orange circle{fill:#fff0df;stroke:#a5652e}.kernel-detail-box.tone-violet rect,.kernel-detail-matrix.tone-violet rect{fill:#eee9f8;stroke:#7156a0}.kernel-detail-frame rect{fill:#fff8ef;fill-opacity:.38;stroke-dasharray:5 4}.kernel-detail-matrix line,.kernel-detail-matrix-depth{fill:none;opacity:.55}.kernel-detail-matrix.tone-blue line,.kernel-detail-matrix.tone-blue .kernel-detail-matrix-depth{stroke:#3b789e}.kernel-detail-matrix.tone-green line,.kernel-detail-matrix.tone-green .kernel-detail-matrix-depth{stroke:#397b63}.kernel-detail-matrix.tone-pink line,.kernel-detail-matrix.tone-pink .kernel-detail-matrix-depth{stroke:#a45d7d}.kernel-detail-matrix.tone-violet line,.kernel-detail-matrix.tone-violet .kernel-detail-matrix-depth{stroke:#7156a0}.kernel-detail-label,.kernel-detail-matrix text,.kernel-detail-operator text,.kernel-detail-text{fill:#27302b;font-size:9px;letter-spacing:0}.kernel-detail-note{fill:#626b65;font-size:7.5px;letter-spacing:0}.kernel-detail-operator text{font-size:13px;font-weight:650}.kernel-detail-text{fill:#5e6862}.kernel-detail-text.emphasis{fill:#27302b;font-size:10px;font-weight:650}.kernel-detail-text.tone-orange{fill:#8d5426}.kernel-node-body{stroke-width:1.35}.kernel-node-title{fill:#202522;font-size:13px;font-weight:650;letter-spacing:0}.kernel-node-title.symbol-label{font-size:10px;font-weight:700}.kernel-node-secondary{fill:#68706a;font-size:10px}.kernel-node-ports{fill:#7c858a;font-size:8px}.kernel-node-symbol{fill:#202522;font-size:25px;font-weight:500}.kernel-node-glyph{fill:none;stroke:currentColor;stroke-width:1;opacity:.62}.shape-tensor .kernel-node-glyph{color:#4f7896}.shape-container .kernel-node-glyph{color:#397b73}.shape-operation .kernel-node-glyph{color:#64727d}.shape-convolution .kernel-node-glyph{color:#397b73}.shape-attention .kernel-node-glyph{color:#a5652e}.shape-normalization .kernel-node-glyph{color:#397662}.kernel-node-glyph rect{fill:#fff}.operation-glyph rect{fill:currentColor;stroke:none}.container-glyph path{fill:none}.kernel-node-glyph-text{fill:currentColor;stroke:none;font-size:7px;font-weight:700;text-anchor:middle}.kernel-expanded-surface{fill:#fff;stroke:#397b73;stroke-width:1.4}.kernel-expanded-header{fill:#edf7f5;stroke:none}.kernel-expanded-module.shape-attention .kernel-expanded-surface{stroke:#a5652e}.kernel-expanded-module.shape-attention .kernel-expanded-header{fill:#fff3e8}.kernel-expanded-module.shape-tensor .kernel-expanded-surface{stroke:#4f7896}.kernel-expanded-module.shape-tensor .kernel-expanded-header{fill:#eef5fb}.kernel-expanded-module.shape-convolution .kernel-expanded-surface{stroke:#397b73}.kernel-expanded-module.shape-convolution .kernel-expanded-header{fill:#edf7f5}.kernel-expanded-module.shape-normalization .kernel-expanded-surface{stroke:#397662}.kernel-expanded-module.shape-normalization .kernel-expanded-header{fill:#eaf6f1}.kernel-expanded-divider{stroke:#cfd5d1;stroke-width:1}.kernel-expanded-title{fill:#202522;font-size:14px;font-weight:650}.kernel-expanded-subtitle{fill:#68706a;font-size:9px}.kernel-export-legend rect{fill:#fff;fill-opacity:.96;stroke:#cfd5d1}.kernel-export-legend text{fill:#303632;font-size:10px}.kernel-export-legend line{stroke-width:2}`;

const SVG_EXPANDED_STYLE = `.kernel-expanded-module.shape-attention .kernel-expanded-surface{stroke:#a35416}.kernel-expanded-module.shape-attention .kernel-expanded-header{fill:#fff3e8}.kernel-expanded-module.shape-tensor .kernel-expanded-surface{stroke:#4f7896}.kernel-expanded-module.shape-tensor .kernel-expanded-header{fill:#eef5fb}.kernel-expanded-module.shape-operation .kernel-expanded-surface{stroke:#64727d}.kernel-expanded-module.shape-operation .kernel-expanded-header{fill:#f7f9fa}.kernel-expanded-module.shape-condition .kernel-expanded-surface{stroke:#966487}.kernel-expanded-module.shape-condition .kernel-expanded-header{fill:#fbf0f8}.kernel-expanded-module.shape-convolution .kernel-expanded-surface{stroke:#397b73}.kernel-expanded-module.shape-convolution .kernel-expanded-header{fill:#edf7f5}.kernel-expanded-module.shape-normalization .kernel-expanded-surface{stroke:#397662}.kernel-expanded-module.shape-normalization .kernel-expanded-header{fill:#eaf6f1}.kernel-expanded-module.shape-merge .kernel-expanded-surface{stroke:#725b19}.kernel-expanded-module.shape-merge .kernel-expanded-header{fill:#faf4df}.kernel-expanded-module.shape-add .kernel-expanded-surface{stroke:#9b5268}.kernel-expanded-module.shape-add .kernel-expanded-header{fill:#f8edf1}`;

export function renderKernelSceneSvg(
  document: KernelDocument,
  visualState: KernelVisualState,
  scene: KernelRenderScene,
): KernelExportArtifact {
  const renderDigest = kernelSceneDigest(document, visualState, scene);
  const bindingById = new Map(document.templateBindings.map((binding) => [binding.bindingId, binding]));
  const nodeByPort = new Map(document.ports.map((port) => [port.portId, port.ownerNodeId]));
  const relations = [...new Set(scene.edges.map((edge) => edge.relation))];
  // The prototype keeps the legend inside the paper; reserving a negative
  // coordinate gutter changes the aspect ratio and makes the same scene look
  // smaller when exported or compared in a browser.
  const exportWidth = scene.width;
  const metadata = escapeXml(JSON.stringify({
    kernelVersion: KERNEL_EXPORT_VERSION,
    renderDigest,
    sceneId: scene.sceneId,
    documentId: document.documentId,
    architectureId: document.architectureId,
    sourceDigest: document.sourceDigest,
  }));
  const expanded = scene.nodes.filter((node) => node.renderRole === "expanded-module").sort((a, b) => a.depth - b.depth)
    .map((node) => renderExpandedNode(node, node.templateBindingId ? bindingById.get(node.templateBindingId)?.fidelity : undefined)).join("");
  const edges = scene.edges.map((edge) => {
    const token = RELATION_TOKENS[edge.relation];
    const plateWidth = Math.max(44, edge.label.length * 6.2);
    const label = visualState.labelStyle === "endpoint" ? "" : `<g class="kernel-edge-label ${visualState.labelStyle}" transform="translate(${edge.labelPoint.x} ${edge.labelPoint.y}) rotate(${edge.labelAngle})">${visualState.labelStyle === "plate" ? `<rect x="${-plateWidth / 2}" y="-9" width="${plateWidth}" height="18" rx="3"/>` : ""}<text text-anchor="middle" y="3">${escapeXml(edge.label)}</text></g>`;
    return `<g class="kernel-edge scene-edge"${data("kernel-edge-id", edge.edgeId)}${data("canonical-edge-ids", edge.canonicalEdgeIds)}${data("source-port-id", edge.sourcePortId)}${data("target-port-id", edge.targetPortId)}${data("evidence-ids", edge.evidenceIds)}><path d="${escapeXml(edge.path)}" stroke="${token.color}"${token.dash ? ` stroke-dasharray="${token.dash}"` : ""} marker-end="url(#kernel-arrow)"/>${label}</g>`;
  }).join("");
  const detailLayer = scene.details.map((detail) => {
    const binding = bindingById.get(detail.bindingId);
    const flows = detail.primitives.filter((primitive) => primitive.kind === "flow")
      .map((primitive) => renderDetailPrimitive(primitive, detail.evidenceIds)).join("");
    const primitives = detail.primitives.filter((primitive) => primitive.kind !== "flow")
      .map((primitive) => renderDetailPrimitive(primitive, detail.evidenceIds)).join("");
    const boundaries = `<circle class="kernel-detail-boundary-portal entry" cx="${detail.entryPoint.x}" cy="${detail.entryPoint.y}" r="4"/><circle class="kernel-detail-boundary-portal exit" cx="${detail.exitPoint.x}" cy="${detail.exitPoint.y}" r="4"/>`;
    return `<g class="kernel-template-detail"${data("kernel-detail-node-id", detail.nodeId)}${data("template-binding-id", detail.bindingId)}${data("template-id", detail.templateId)}${data("template-fidelity", binding?.fidelity)}${data("evidence-ids", detail.evidenceIds)}>${flows}${primitives}${boundaries}</g>`;
  }).join("");
  const portals = scene.portals.map((portal) => `<circle class="kernel-portal ${portal.direction}" cx="${portal.point.x}" cy="${portal.point.y}" r="3.4"${data("portal-id", portal.portalId)}${data("module-node-id", portal.moduleNodeId)}${data("kernel-edge-id", portal.edgeId)}/>`).join("");
  const standard = scene.nodes.filter((node) => node.renderRole !== "expanded-module").map((node) => renderStandardNode(
    node,
    visualState.nodeStyle,
    scene.edges.filter((edge) => nodeByPort.get(edge.targetPortId) === node.nodeId).length,
    scene.edges.filter((edge) => nodeByPort.get(edge.sourcePortId) === node.nodeId).length,
    node.templateBindingId ? bindingById.get(node.templateBindingId)?.fidelity : undefined,
  )).join("");
  const endpointLabels = visualState.labelStyle === "endpoint" ? scene.edges.map((edge) => {
    const targetId = nodeByPort.get(edge.targetPortId);
    const target = scene.nodes.find((node) => node.nodeId === targetId);
    return target ? `<text${data("kernel-edge-id", edge.edgeId)} x="${target.bounds.x + 8}" y="${target.bounds.y - 7}">${escapeXml(edge.label)}</text>` : "";
  }).join("") : "";
  const legendHeight = 16 + relations.length * 17;
  const legend = `<g class="kernel-export-legend" data-relation-count="${relations.length}" transform="translate(20 20)"><rect width="108" height="${legendHeight}" rx="5"/>${relations.map((relation, index) => {
    const token = RELATION_TOKENS[relation];
    const y = 17 + index * 17;
    return `<g${data("relation", relation)}><line x1="9" y1="${y - 3}" x2="31" y2="${y - 3}" stroke="${token.color}"${token.dash ? ` stroke-dasharray="${token.dash}"` : ""}/><text x="38" y="${y}">${escapeXml(token.label)}</text></g>`;
  }).join("")}</g>`;
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${exportWidth}" height="${scene.height}" viewBox="0 0 ${exportWidth} ${scene.height}" role="img" aria-label="Model architecture"${data("kernel-version", KERNEL_EXPORT_VERSION)}${data("kernel-scene-id", scene.sceneId)}${data("architecture-id", document.architectureId)}${data("source-digest", document.sourceDigest)}${data("render-digest", renderDigest)}><metadata>${metadata}</metadata><style>${SVG_STYLE}${SVG_EXPANDED_STYLE}</style><defs><pattern id="kernel-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0L0 0 0 20" fill="none"/></pattern><marker id="kernel-arrow" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="5.8" markerHeight="5.8" orient="auto"><path d="M0 1 9 5 0 9Z" fill="context-stroke"/></marker><marker id="kernel-detail-arrow" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="4.8" markerHeight="4.8" orient="auto"><path d="M0 1 9 5 0 9Z" fill="context-stroke"/></marker></defs><rect class="kernel-paper" x="0" width="${exportWidth}" height="${scene.height}"/><rect class="kernel-grid" x="12" y="12" width="${Math.max(0, scene.width - 24)}" height="${Math.max(0, scene.height - 24)}" fill="url(#kernel-grid)"/><g class="kernel-expanded-layer">${expanded}</g><g class="kernel-edge-layer">${edges}</g><g class="kernel-detail-layer">${detailLayer}</g><g class="kernel-portal-layer">${portals}</g><g class="kernel-node-layer">${standard}</g><g class="kernel-endpoint-labels">${endpointLabels}</g>${legend}</svg>`;
  return {
    svg,
    renderDigest,
    width: exportWidth,
    height: scene.height,
    sceneId: scene.sceneId,
    sourceDigest: document.sourceDigest,
  };
}
