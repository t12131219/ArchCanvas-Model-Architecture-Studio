import { measureScene, routeScene } from "./routing";
import { buildInlineDetailLayout } from "./detail-layout";
import type { DetailExpansionMap, DetailLayoutMap, InlineDetailLevel } from "./detail-layout";
import {
  buildAtomicHierarchyProjection,
  projectedAtomicExit,
  projectedNestedExitBridgeIds,
  projectedSceneBoundaryPorts,
} from "./atomic-hierarchy";
import { DETAIL_KIND_NAMES } from "./module-details";
import type { DetailPrimitive } from "./module-details";
import type {
  EdgeLabelStyle,
  EdgeRelation,
  HierarchyRoutingMode,
  LabNode,
  LabScene,
  NodeShape,
  NodeVisualStyle,
  Point,
  RoutedEdge,
  SceneMetrics,
  VisualOptions,
} from "./types";

const RELATION_COLORS: Record<EdgeRelation, string> = {
  flow: "#39444d",
  branch: "#266d66",
  merge: "#725b19",
  residual: "#b33d5a",
  memory: "#7756a2",
  condition: "#a35416",
  feedback: "#2467a5",
};

const NODE_COLORS: Record<NodeShape, { fill: string; stroke: string }> = {
  operation: { fill: "#f7f9fa", stroke: "#64727d" },
  tensor: { fill: "#eef5fb", stroke: "#4f7896" },
  convolution: { fill: "#edf7f5", stroke: "#397b73" },
  attention: { fill: "#fff3e8", stroke: "#a5652e" },
  normalization: { fill: "#eaf6f1", stroke: "#397662" },
  condition: { fill: "#fbf0f8", stroke: "#966487" },
  merge: { fill: "#f8f2df", stroke: "#8d742d" },
  add: { fill: "#fff4cf", stroke: "#8d742d" },
  multiply: { fill: "#fcebdc", stroke: "#a35416" },
  concat: { fill: "#eeeaf8", stroke: "#72549b" },
  io: { fill: "#f8edf1", stroke: "#9b5268" },
};

function escapeXml(value: string): string {
  return value.replace(/[<>&"']/g, (character) => ({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "\"": "&quot;",
    "'": "&apos;",
  })[character]!);
}

function wrapLabel(value: string, maxCharacters: number): string[] {
  if (value.length <= maxCharacters) return [value];
  const words = value.includes(" ") ? value.split(/\s+/) : [...value];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current}${value.includes(" ") ? " " : ""}${word}` : word;
    if (candidate.length > maxCharacters && current) {
      lines.push(current);
      current = word;
    } else current = candidate;
  }
  if (current) lines.push(current);
  return lines.slice(0, 3);
}

function polygonPoints(node: LabNode): string | null {
  const { x, y, width, height } = node.bounds;
  if (node.shape === "condition") {
    const inset = Math.min(25, width * 0.16);
    return `${x + inset},${y} ${x + width - inset},${y} ${x + width},${y + height / 2} ${x + width - inset},${y + height} ${x + inset},${y + height} ${x},${y + height / 2}`;
  }
  if (node.shape === "merge") {
    return `${x + width / 2},${y} ${x + width},${y + height / 2} ${x + width / 2},${y + height} ${x},${y + height / 2}`;
  }
  return null;
}

function matrixGrid(x: number, y: number, width: number, height: number, stroke: string, columns = 4, rows = 3): string {
  const vertical = Array.from({ length: columns - 1 }, (_, index) => {
    const lineX = x + width * (index + 1) / columns;
    return `<line x1="${lineX}" y1="${y}" x2="${lineX}" y2="${y + height}"/>`;
  }).join("");
  const horizontal = Array.from({ length: rows - 1 }, (_, index) => {
    const lineY = y + height * (index + 1) / rows;
    return `<line x1="${x}" y1="${lineY}" x2="${x + width}" y2="${lineY}"/>`;
  }).join("");
  return `<g class="node-grid" stroke="${stroke}">${vertical}${horizontal}</g>`;
}

function renderDetailPrimitive(primitive: DetailPrimitive, atomicEdgeId?: string): string {
  if (primitive.kind === "flow") {
    const points = primitive.points.map((point) => `${point.x},${point.y}`).join(" ");
    const toneClass = primitive.tone ? ` detail-tone-${primitive.tone}` : "";
    const markerId = primitive.tone && primitive.tone !== "neutral" ? `internal-arrow-${primitive.tone}` : "internal-arrow";
    const marker = primitive.marker === false ? "" : ` marker-end="url(#${markerId})"`;
    const edgeId = atomicEdgeId ? ` data-atomic-edge-id="${escapeXml(atomicEdgeId)}"` : "";
    return `<polyline class="detail-flow${toneClass}"${edgeId} points="${points}"${marker}/>`;
  }
  if (primitive.kind === "text") {
    const classes = ["detail-text", primitive.emphasis ? "emphasis" : "", primitive.tone ? `detail-tone-${primitive.tone}` : ""].filter(Boolean).join(" ");
    return `<text class="${classes}" x="${primitive.x}" y="${primitive.y}" text-anchor="${primitive.anchor ?? "middle"}">${escapeXml(primitive.value)}</text>`;
  }
  if (primitive.kind === "circle") {
    return `<g class="detail-shape detail-tone-${primitive.tone}"><circle cx="${primitive.cx}" cy="${primitive.cy}" r="${primitive.radius}"/><text class="detail-symbol" x="${primitive.cx}" y="${primitive.cy + 5}">${escapeXml(primitive.label)}</text></g>`;
  }
  if (primitive.kind === "matrix") {
    const depth = Array.from({ length: primitive.depth ? 2 : 0 }, (_, depthIndex) => `<rect x="${primitive.x + (2 - depthIndex) * 4}" y="${primitive.y - (2 - depthIndex) * 4}" width="${primitive.width}" height="${primitive.height}" rx="2"/>`).join("");
    const label = primitive.label ? `<text class="detail-matrix-label" x="${primitive.x + primitive.width / 2}" y="${primitive.y - 7}">${escapeXml(primitive.label)}</text>` : "";
    return `<g class="detail-shape detail-matrix detail-tone-${primitive.tone}">${depth}<rect x="${primitive.x}" y="${primitive.y}" width="${primitive.width}" height="${primitive.height}" rx="2"/>${matrixGrid(primitive.x, primitive.y, primitive.width, primitive.height, "currentColor", primitive.columns, primitive.rows)}${label}</g>`;
  }
  const label = primitive.label ? `<text class="detail-box-label" x="${primitive.x + primitive.width / 2}" y="${primitive.y + primitive.height / 2 + (primitive.note ? -2 : 4)}">${escapeXml(primitive.label)}</text>` : "";
  const note = primitive.note ? `<text class="detail-note" x="${primitive.x + primitive.width / 2}" y="${primitive.y + primitive.height / 2 + 13}">${escapeXml(primitive.note)}</text>` : "";
  return `<g class="detail-shape detail-tone-${primitive.tone} detail-${primitive.variant ?? "box"}"><rect x="${primitive.x}" y="${primitive.y}" width="${primitive.width}" height="${primitive.height}" rx="${primitive.rx}"/>${label}${note}</g>`;
}

function renderInlineDetailLevel(level: InlineDetailLevel, hiddenFlowIds: ReadonlySet<string>): string {
  const expanded = level.expandedChild;
  const primitives = level.diagram.primitives.map((primitive, index) => {
    const node = level.nodes.find((item) => item.primitiveIndex === index);
    const atomicEdgeId = primitive.kind === "flow" ? `${level.levelKey}:flow:${index}` : undefined;
    if (expanded && node?.id === expanded.node.id) return "";
    if (atomicEdgeId && hiddenFlowIds.has(atomicEdgeId)) return "";
    return renderDetailPrimitive(primitive, atomicEdgeId);
  }).join("");
  if (!expanded) return primitives;
  const { x, y, width, height } = expanded.node.bounds;
  const nested = renderInlineDetailLevel(expanded.level, hiddenFlowIds);
  const expandedMarkup = `<g class="nested-inline-detail" data-detail-node-id="${escapeXml(expanded.node.id)}"><rect class="nested-inline-surface" x="${x}" y="${y}" width="${width}" height="${height}" rx="5"/><g class="detail-level detail-${expanded.level.kind}">${nested}</g><rect class="nested-inline-header" x="${x}" y="${y}" width="${width}" height="42" rx="5"/><line class="nested-inline-divider" x1="${x}" y1="${y + 42}" x2="${x + width}" y2="${y + 42}"/><text class="nested-detail-title" x="${x + 12}" y="${y + 17}">${escapeXml(expanded.node.label)}</text><text class="nested-detail-subtitle" x="${x + 12}" y="${y + 32}">${escapeXml(DETAIL_KIND_NAMES[expanded.level.kind])}</text></g>`;
  return `${expandedMarkup}${primitives}`;
}

function renderExpandedNode(node: LabNode, level: InlineDetailLevel, hiddenFlowIds: ReadonlySet<string>): string {
  const { x, y, width, height } = node.bounds;
  const colors = NODE_COLORS[node.shape];
  const detail = renderInlineDetailLevel(level, hiddenFlowIds);
  return `<g class="scene-node expanded-node" data-node-id="${escapeXml(node.scene_node_id)}"><rect class="node-surface expanded-surface" x="${x}" y="${y}" width="${width}" height="${height}" rx="6" fill="#fff" stroke="${colors.stroke}"/><rect class="expanded-header" x="${x}" y="${y}" width="${width}" height="50" rx="6" fill="${colors.fill}"/><line class="expanded-divider" x1="${x}" y1="${y + 50}" x2="${x + width}" y2="${y + 50}"/><text class="expanded-title" x="${x + 16}" y="${y + 22}">${escapeXml(node.label)}</text><text class="expanded-subtitle" x="${x + 16}" y="${y + 39}">${escapeXml(DETAIL_KIND_NAMES[level.kind])}</text><g class="module-detail detail-${level.kind}">${detail}</g></g>`;
}

function renderNode(
  node: LabNode,
  style: NodeVisualStyle,
  detailTree?: InlineDetailLevel,
  hiddenFlowIds: ReadonlySet<string> = new Set(),
): string {
  if (node.detail_expanded && node.detail_kind && detailTree) return renderExpandedNode(node, detailTree, hiddenFlowIds);
  const { x, y, width, height } = node.bounds;
  const colors = NODE_COLORS[node.shape];
  const fill = style === "compact" ? "#ffffff" : colors.fill;
  const polygon = polygonPoints(node);
  const symbol = node.shape === "add" ? "+" : node.shape === "multiply" ? "&#215;" : node.shape === "concat" ? "||" : null;
  const detailed = ["tensor", "convolution", "attention", "normalization"].includes(node.shape) && width >= 110;
  const labelX = detailed ? x + width * 0.68 : x + width / 2;
  const labelWidth = detailed ? width * 0.53 : width - 22;
  const shape = symbol
    ? `<circle class="node-surface" cx="${x + width / 2}" cy="${y + height * 0.42}" r="${Math.min(width, height) * 0.27}" fill="${fill}" stroke="${colors.stroke}"/><text class="node-symbol" x="${x + width / 2}" y="${y + height * 0.42 + 8}">${symbol}</text>`
    : polygon
      ? `<polygon class="node-surface" points="${polygon}" fill="${fill}" stroke="${colors.stroke}"/>`
      : `<rect class="node-surface" x="${x}" y="${y}" width="${width}" height="${height}" rx="${node.shape === "io" ? Math.min(26, height / 2) : node.shape === "normalization" ? 14 : 5}" fill="${fill}" stroke="${colors.stroke}"/>`;
  const glyphX = x + 12;
  const glyphY = y + Math.max(11, (height - Math.min(44, height - 22)) / 2);
  const glyphWidth = Math.min(52, width * 0.37);
  const glyphHeight = Math.min(44, height - 22);
  let glyph = "";
  if (node.shape === "tensor" && detailed) {
    glyph = `<g class="node-glyph" stroke="${colors.stroke}"><path d="M ${glyphX + 6} ${glyphY - 6} h ${glyphWidth} l 7 7 v ${glyphHeight} l -7 -7 h -${glyphWidth} z" fill="none"/><rect x="${glyphX}" y="${glyphY}" width="${glyphWidth}" height="${glyphHeight}" rx="2" fill="${fill}"/>${matrixGrid(glyphX, glyphY, glyphWidth, glyphHeight, colors.stroke)}</g>`;
  } else if (node.shape === "convolution" && detailed) {
    const stack = [8, 4, 0].map((offset) => `<rect x="${glyphX + offset}" y="${glyphY - offset}" width="${glyphWidth - 8}" height="${glyphHeight}" rx="2" fill="${fill}"/>`).join("");
    glyph = `<g class="node-glyph" stroke="${colors.stroke}">${stack}${matrixGrid(glyphX + 8, glyphY - 8, glyphWidth - 8, glyphHeight, colors.stroke, 3, 3)}</g>`;
  } else if (node.shape === "attention" && detailed) {
    const qkv = ["Q", "K", "V"].map((value, index) => `<g><rect x="${glyphX}" y="${glyphY + index * glyphHeight / 3}" width="17" height="${glyphHeight / 3 - 2}" rx="2" fill="${fill}"/><text class="node-glyph-text" x="${glyphX + 8.5}" y="${glyphY + index * glyphHeight / 3 + glyphHeight / 6 + 3}">${value}</text><line x1="${glyphX + 18}" y1="${glyphY + index * glyphHeight / 3 + glyphHeight / 6}" x2="${glyphX + glyphWidth - 8}" y2="${glyphY + glyphHeight / 2}"/></g>`).join("");
    glyph = `<g class="node-glyph" stroke="${colors.stroke}">${qkv}<circle cx="${glyphX + glyphWidth - 5}" cy="${glyphY + glyphHeight / 2}" r="5" fill="${fill}"/></g>`;
  } else if (node.shape === "normalization" && detailed) {
    const bars = [-0.26, 0, 0.26].map((ratio) => `<line x1="${glyphX + glyphWidth / 2 + ratio * glyphWidth}" y1="${glyphY + 8}" x2="${glyphX + glyphWidth / 2 + ratio * glyphWidth}" y2="${glyphY + glyphHeight - 8}"/>`).join("");
    glyph = `<g class="node-glyph" stroke="${colors.stroke}"><rect x="${glyphX}" y="${glyphY}" width="${glyphWidth}" height="${glyphHeight}" rx="${glyphHeight / 2}" fill="${fill}"/>${bars}<text class="node-glyph-text" x="${glyphX + glyphWidth / 2}" y="${glyphY + glyphHeight / 2 + 3}">&#956; &#963;</text></g>`;
  } else if (node.shape === "operation" && width >= 100) {
    glyph = `<g class="node-glyph operation-glyph" stroke="${colors.stroke}">${[0, 1, 2].map((index) => `<rect x="${x + 10}" y="${y + 13 + index * 11}" width="${15 + index * 3}" height="6" rx="1.5" fill="${colors.stroke}"/>`).join("")}</g>`;
  }
  const maxCharacters = Math.max(5, Math.floor(labelWidth / (style === "compact" ? 7.1 : 6.7)));
  const lines = wrapLabel(node.label, maxCharacters);
  const titleY = style === "technical" ? y + 31 : y + height / 2 - (lines.length - 1) * 8 - (style !== "compact" && height >= 62 ? 4 : 0);
  const textX = symbol ? x + width / 2 : labelX;
  const textY = symbol ? y + height - 8 : titleY;
  const text = lines.map((line, index) => `<tspan x="${textX}" dy="${index ? 16 : 0}">${escapeXml(line)}</tspan>`).join("");
  const detail = symbol || style === "compact" || height < 58
    ? ""
    : `<text class="node-detail" x="${labelX}" y="${y + height - 11}">${escapeXml(node.secondary_label)}</text>`;
  const rail = style === "technical" && !symbol
    ? `<rect x="${x}" y="${y}" width="5" height="${height}" rx="2" fill="${colors.stroke}"/><text class="node-kind" x="${x + 13}" y="${y + 14}">${node.shape.toUpperCase()}</text>`
    : "";
  return `<g class="scene-node node-${style}" data-node-id="${escapeXml(node.scene_node_id)}">${shape}${glyph}${rail}<text class="node-label${symbol ? " symbol-label" : ""}" x="${textX}" y="${textY}">${text}</text>${detail}</g>`;
}

function edgeLabelPoint(route: RoutedEdge, style: EdgeLabelStyle): Point & { angle: number } {
  if (style !== "endpoint") return { x: route.labelPoint.x, y: route.labelPoint.y, angle: route.labelAngle };
  const end = route.points.at(-1)!;
  const previous = route.points.at(-2)!;
  const vertical = Math.abs(end.y - previous.y) > Math.abs(end.x - previous.x);
  return {
    x: end.x + (previous.x - end.x) * 0.48,
    y: end.y + (previous.y - end.y) * 0.48,
    angle: vertical ? -90 : 0,
  };
}

function renderEdge(route: RoutedEdge, labelStyle: EdgeLabelStyle): string {
  const color = RELATION_COLORS[route.edge.relation];
  const labelPoint = edgeLabelPoint(route, labelStyle);
  const labelWidth = Math.max(42, Math.min(220, route.edge.label.length * 6.6 + 16));
  const plate = labelStyle === "plate"
    ? `<rect class="edge-label-plate" x="${labelPoint.x - labelWidth / 2}" y="${labelPoint.y - 17}" width="${labelWidth}" height="18" rx="3"/>`
    : "";
  const dash = route.edge.relation === "residual" || route.edge.relation === "feedback" ? " stroke-dasharray=\"7 5\"" : "";
  const marker = route.markerEnd === false ? "" : ` marker-end="url(#arrow-${route.edge.relation})"`;
  return `<g class="scene-edge relation-${route.edge.relation}" data-edge-id="${escapeXml(route.edge.scene_edge_id)}"><path d="${route.path}" fill="none" stroke="${color}"${dash}${marker} vector-effect="non-scaling-stroke"/><g transform="rotate(${labelPoint.angle} ${labelPoint.x} ${labelPoint.y})">${plate}<text class="edge-label" x="${labelPoint.x}" y="${labelPoint.y - 4}">${escapeXml(route.edge.label)}</text></g></g>`;
}

function renderMarkers(): string {
  const external = Object.entries(RELATION_COLORS).map(([relation, color]) => `<marker id="arrow-${relation}" viewBox="0 0 10 10" refX="8.8" refY="5" markerWidth="5.8" markerHeight="5.8" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 z" fill="${color}"/></marker>`).join("");
  const internal = Object.entries({ neutral: "#68706a", blue: "#3b789e", green: "#397b63", pink: "#a45d7d", orange: "#a5652e", violet: "#7156a0" })
    .map(([tone, color]) => `<marker id="${tone === "neutral" ? "internal-arrow" : `internal-arrow-${tone}`}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="4.8" markerHeight="4.8" orient="auto"><path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="${color}"/></marker>`)
    .join("");
  return `${external}${internal}`;
}

export function renderSceneSvg(
  scene: LabScene,
  options: VisualOptions,
  detailLayouts: DetailLayoutMap = {},
  detailExpansions: DetailExpansionMap = {},
  hierarchyRoutingMode: HierarchyRoutingMode = "atomic-bottom-up",
): { svg: string; metrics: SceneMetrics } {
  const detailTrees: Record<string, InlineDetailLevel> = Object.fromEntries(scene.nodes.flatMap((node) => (
    node.detail_expanded && node.detail_kind
      ? [[node.scene_node_id, buildInlineDetailLayout(
        node.detail_kind,
        node.bounds,
        detailExpansions[node.scene_node_id],
        detailLayouts,
        node.scene_node_id,
        [],
        hierarchyRoutingMode,
      )]]
      : []
  )));
  const projections = hierarchyRoutingMode === "atomic-bottom-up"
    ? Object.fromEntries(Object.entries(detailTrees).map(([nodeId, tree]) => [
      nodeId,
      buildAtomicHierarchyProjection(tree),
    ]))
    : {};
  const boundaryPorts = hierarchyRoutingMode === "atomic-bottom-up"
    ? projectedSceneBoundaryPorts(projections)
    : undefined;
  const outgoingNodeIds = new Set(scene.edges.map((edge) => edge.source_scene_node_id));
  const hiddenExitBridgeIds = hierarchyRoutingMode === "atomic-bottom-up"
    ? new Set(Object.entries(projections).flatMap(([nodeId, projection]) => [
      ...projectedNestedExitBridgeIds(projection),
      ...(outgoingNodeIds.has(nodeId) ? projectedAtomicExit(projection)?.bridgeEdgeIds ?? [] : []),
    ]))
    : new Set<string>();
  const routed = routeScene(scene, options.routeStyle, boundaryPorts);
  const metrics = measureScene(scene, routed);
  const backgroundEdges = routed.filter((route) => !route.foreground)
    .map((route) => renderEdge(route, options.labelStyle)).join("");
  const foregroundEdges = routed.filter((route) => route.foreground)
    .map((route) => renderEdge(route, options.labelStyle)).join("");
  const nodes = scene.nodes.map((item) => renderNode(
    item,
    options.nodeStyle,
    detailTrees[item.scene_node_id],
    hiddenExitBridgeIds,
  )).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="scene-title scene-description" viewBox="0 0 ${scene.paper_width} ${scene.paper_height}">
  <title id="scene-title">${escapeXml(scene.title)}</title><desc id="scene-description">${escapeXml(scene.description)}</desc>
  <defs>${renderMarkers()}<pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="#dfe3e1" stroke-width=".7"/></pattern></defs>
  <style>
    text{font-family:Inter,ui-sans-serif,system-ui,sans-serif;letter-spacing:0}.scene-node>*{vector-effect:non-scaling-stroke;stroke-width:1.35}.node-label{fill:#202522;font-size:13px;font-weight:650;text-anchor:middle}.node-label.symbol-label{font-size:10px;font-weight:700}.node-detail{fill:#68706a;font-size:10px;text-anchor:middle}.node-kind{fill:#68706a;font-size:8px;font-weight:750}.node-symbol{fill:#202522;stroke:none;font-size:25px;font-weight:500;text-anchor:middle}.node-glyph *,.node-grid *{vector-effect:non-scaling-stroke;stroke-width:1px}.node-grid{opacity:.5}.node-glyph-text{fill:#303632;stroke:none;font-size:7px;font-weight:700;text-anchor:middle}.operation-glyph{opacity:.48}.scene-edge path{stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round}.edge-label{fill:#303632;font-size:10px;font-weight:650;text-anchor:middle;paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}.edge-label-plate{fill:#fff;stroke:#cfd5d1;stroke-width:1px;vector-effect:non-scaling-stroke}.node-compact .node-label{font-size:12px}.node-compact .node-detail{display:none}.expanded-header{stroke:none}.expanded-divider{stroke:#cfd5d1;stroke-width:1px}.expanded-title{fill:#202522;font-size:14px;font-weight:650;text-anchor:start}.expanded-subtitle{fill:#68706a;font-size:9px;text-anchor:start}.detail-flow{fill:none;stroke:#68706a;stroke-width:1.25px;stroke-linecap:round;stroke-linejoin:round}.detail-flow.detail-tone-blue{stroke:#3b789e}.detail-flow.detail-tone-green{stroke:#397b63}.detail-flow.detail-tone-pink{stroke:#a45d7d}.detail-flow.detail-tone-orange{stroke:#a5652e}.detail-flow.detail-tone-violet{stroke:#7156a0}.detail-shape{color:#69736d}.detail-shape rect,.detail-shape circle{fill:#f4f6f4;stroke:currentColor;stroke-width:1.1px}.detail-tone-blue{color:#3b789e}.detail-tone-blue rect,.detail-tone-blue circle{fill:#e5f3fb}.detail-tone-green{color:#397b63}.detail-tone-green rect,.detail-tone-green circle{fill:#e6f5ec}.detail-tone-pink{color:#a45d7d}.detail-tone-pink rect,.detail-tone-pink circle{fill:#f9e7ef}.detail-tone-orange{color:#a5652e}.detail-tone-orange rect,.detail-tone-orange circle{fill:#fff0df}.detail-tone-violet{color:#7156a0}.detail-tone-violet rect,.detail-tone-violet circle{fill:#eee9f8}.detail-frame>rect{fill:#fff8ef;stroke-width:1.4px}.detail-matrix .node-grid{opacity:.55}.detail-matrix-label,.detail-box-label,.detail-symbol{fill:#27302b;stroke:none;font-size:9px;font-weight:650;text-anchor:middle}.detail-symbol{font-size:17px;font-weight:500}.detail-note{fill:#626b65;stroke:none;font-size:7.5px;text-anchor:middle}.detail-text{fill:#5e6862;font-size:8.5px;font-weight:400}.detail-text.emphasis{fill:#27302b;font-size:10px;font-weight:650}.detail-text.detail-tone-orange{fill:#8d5426}.nested-inline-surface{fill:#fff;stroke:#87928b;stroke-width:1.4px}.nested-inline-header{fill:#f3f6f3}.nested-inline-divider{stroke:#cbd3ce;stroke-width:1px}.nested-detail-title{fill:#202522;font-size:11px;font-weight:650;text-anchor:start}.nested-detail-subtitle{fill:#68706a;font-size:8px;text-anchor:start}
  </style>
  <rect width="100%" height="100%" fill="#f7f8f6"/><rect x="12" y="12" width="${scene.paper_width - 24}" height="${scene.paper_height - 24}" fill="url(#grid)" stroke="#cfd5d1"/>${backgroundEdges}${nodes}${foregroundEdges}
</svg>`;
  return { svg, metrics };
}

function htmlEscape(value: string): string {
  return escapeXml(value);
}

export function renderCaseIndex(
  scene: LabScene,
  variants: Array<{ name: string; options: VisualOptions; metrics: SceneMetrics }>,
  expansionVariants: Array<{ name: string; label: string; metrics: SceneMetrics }> = [],
): string {
  const expansionItems = expansionVariants.map(({ name, label, metrics }) => `<article class="expansion-case"><a href="./${name}.svg"><img loading="lazy" src="./${name}.svg" alt="${htmlEscape(scene.title)} ${htmlEscape(label)}"/></a><div><strong>${htmlEscape(label)}</strong><span>穿越 ${metrics.nodeIntersections} · 净距 ${metrics.clearanceViolations} · 端口 ${metrics.endpointCongestion} · 反向 ${metrics.reverseExits}</span><a href="./${name}.json">JSON</a></div></article>`).join("");
  const items = variants.map(({ name, options, metrics }) => `<article><a href="./${name}.svg"><img loading="lazy" src="./${name}.svg" alt="${htmlEscape(scene.title)} ${name}"/></a><div><strong>${options.routeStyle} · ${options.nodeStyle} · ${options.labelStyle}</strong><span>交叉 ${metrics.crossings} · 重叠 ${metrics.overlaps} · 净距 ${metrics.clearanceViolations} · 端口 ${metrics.endpointCongestion} · 反向 ${metrics.reverseExits}</span><a href="./${name}.json">JSON</a></div></article>`).join("");
  const expansionCount = expansionVariants.length ? ` · ${expansionVariants.length} 张展开快照` : "";
  return `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><link rel="icon" href="data:,"/><title>${htmlEscape(scene.title)} · ArchCanvas Scene Lab</title><style>${galleryCss()}</style></head><body><header><a href="../index.html">全部场景</a><h1>${htmlEscape(scene.title)}</h1><p>${htmlEscape(scene.description)} · ${variants.length} 种组合${expansionCount}</p></header><main class="grid">${expansionItems}${items}</main></body></html>`;
}

export function renderGalleryIndex(scenes: readonly LabScene[]): string {
  const items = scenes.map((scene) => `<article><a href="./${scene.scene_id}/index.html"><img loading="lazy" src="./${scene.scene_id}/adaptive-semantic-plate.svg" alt="${htmlEscape(scene.title)}"/></a><div><strong>${htmlEscape(scene.title)}</strong><span>${htmlEscape(scene.description)}</span><a href="./${scene.scene_id}/index.html">查看 45 种组合</a></div></article>`).join("");
  return `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><link rel="icon" href="data:,"/><title>ArchCanvas Scene Lab · 案例矩阵</title><style>${galleryCss()}</style></head><body><header><a href="../index.html">返回编辑器</a><h1>案例矩阵</h1><p>${scenes.length} 类拓扑 · 5 种布线 · 3 种节点视觉 · 3 种标签，共 ${scenes.length * 45} 个组合</p></header><main class="grid">${items}</main></body></html>`;
}

function galleryCss(): string {
  return `:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#202522;background:#eef0ed;letter-spacing:0}*{box-sizing:border-box}body{margin:0}header{position:sticky;top:0;z-index:2;padding:16px 22px;border-bottom:1px solid #cfd5d1;background:rgba(255,255,255,.96)}header a,article a{color:#245f9d;text-decoration:none}h1{margin:6px 0 2px;font-size:22px}p{margin:0;color:#656c67;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;padding:16px}article{min-width:0;border:1px solid #cbd1cd;border-radius:6px;background:#fff;overflow:hidden}article img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#f7f8f6;border-bottom:1px solid #d9dedb}article div{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 12px;padding:10px 12px}article strong,article span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}article span{grid-column:1/-1;color:#6a716c;font-size:11px}article a{font-size:11px}@media(max-width:520px){.grid{grid-template-columns:1fr;padding:8px}header{padding:12px 14px}}`;
}
